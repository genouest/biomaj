from builtins import str
from builtins import object
import os
import logging
import time
import shutil
# import copy

from datetime import datetime
from biomaj.mongo_connector import MongoConnector

from biomaj.session import Session
from biomaj.workflow import UpdateWorkflow, RemoveWorkflow, Workflow
from biomaj.config import BiomajConfig
from biomaj.options import Options
from biomaj.process.processfactory import ProcessFactory
from biomaj.bmajindex import BmajIndex


# from bson.objectid import ObjectId


class Bank(object):
    '''
    BioMAJ bank
    '''

    def __init__(self, name, options=None, no_log=False):
        '''
        Get a bank from db or creates a new one

        :param name: name of the bank, must match its config file
        :type name: str
        :param options: bank options
        :type options: argparse
        :param no_log: create a log file for the bank
        :type no_log: bool
        '''
        logging.debug('Initialize ' + name)
        if BiomajConfig.global_config is None:
            raise Exception('Configuration must be loaded first')

        self.name = name
        self.depends = []
        self.no_log = no_log

        if no_log:
            if options is None:
                # options = {'no_log': True}
                options = Options()
                options.no_log = True
            else:
                options.no_log = no_log

        self.config = BiomajConfig(self.name, options)

        if self.config.get('bank.num.threads') is not None:
            ProcessFactory.NB_THREAD = int(self.config.get('bank.num.threads'))

        if self.config.log_file is not None and self.config.log_file != 'none':
            logging.info("Log file: " + self.config.log_file)

        # self.options = Options(options)
        if options is None:
            self.options = Options()
        else:
            self.options = options

        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        self.banks = MongoConnector.banks

        self.bank = self.banks.find_one({'name': self.name})

        if self.bank is None:
            self.bank = {
                'name': self.name,
                'current': None,
                'sessions': [],
                'production': [],
                'properties': self.get_properties()
            }
            self.bank['_id'] = self.banks.insert(self.bank)

        self.session = None
        self.use_last_session = False

    def check(self):
        '''
        Checks bank configuration
        '''
        return self.config.check()

    def is_locked(self):
        '''
        Checks if bank is locked ie action is in progress
        '''
        data_dir = self.config.get('data.dir')
        lock_dir = self.config.get('lock.dir', default=data_dir)
        lock_file = os.path.join(lock_dir, self.name + '.lock')
        if os.path.exists(lock_file):
            return True
        else:
            return False

    def get_bank(self):
        '''
        Get bank stored in db

        :return: bank json object
        '''
        return self.bank

    @staticmethod
    def get_banks_disk_usage():
        '''
        Get disk usage per bank and release
        '''
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        bank_list = []
        banks = MongoConnector.banks.find({}, {'name': 1, 'production': 1})
        for b in banks:
            bank_elt = {'name': b['name'], 'size': 0, 'releases': []}
            for p in b['production']:
                if p['size'] is None:
                    p['size'] = 0
                bank_elt['size'] += p['size']
                bank_elt['releases'].append({'name': p['release'], 'size': p['size']})
            bank_list.append(bank_elt)
        return bank_list

    def get_bank_release_info(self, full=False):
        '''
        Get release info for the bank. Used with --status option from biomaj-cly.py
        :param full: Display full for the bank
        :type full: Boolean
        :return: Dict with keys
                      if full=True
                           - info, prod, pending
                      else
                           - info
        '''

        _bank = self.bank
        info = {}

        if full:
            bank_info = []
            prod_info = []
            pend_info = []
            release = None
            if 'current' in _bank and _bank['current']:
                for prod in _bank['production']:
                    if _bank['current'] == prod['session']:
                        release = prod['release']
            # Bank info header
            bank_info.append(["Name", "Type(s)", "Last update status", "Published release"])
            bank_info.append([_bank['name'],
                              str(','.join(_bank['properties']['type'])),
                              str(datetime.fromtimestamp(_bank['last_update_session']).strftime("%Y-%m-%d %H:%M:%S")),
                              str(release)])
            # Bank production info header
            prod_info.append(["Session", "Remote release", "Release", "Directory", "Freeze", "Pending"])
            for prod in _bank['production']:
                release_dir = os.path.join(self.config.get('data.dir'),
                                           self.config.get('dir.version'),
                                           prod['prod_dir'])
                date = datetime.fromtimestamp(prod['session']).strftime('%Y-%m-%d %H:%M:%S')
                prod_info.append([date,
                                  prod['remoterelease'],
                                  prod['release'],
                                  release_dir,
                                  'yes' if 'freeze' in prod and prod['freeze'] else 'no'])
            # Bank pending info header
            if 'pending' in _bank and len(_bank['pending'].keys()) > 0:
                pend_info.append(["Pending release(s)"])
                for pending in _bank['pending'].keys():
                    pend_info.append(pending)
            # return [ bank_info, prod_info, pend_info ]
            info['info'] = bank_info
            info['prod'] = prod_info
            info['pend'] = pend_info
            return info

        else:
            if 'current' in _bank and _bank['current']:
                for prod in _bank['production']:
                    if _bank['current'] == prod['session']:
                        release = prod['remoterelease']
            else:
                release = 'N/A'
            # return [ _bank['name'], ','.join(_bank['properties']['type']), str(release), _bank['properties']['visibility'] ]
            info['info'] = [_bank['name'], ','.join(_bank['properties']['type']),
                            str(release), _bank['properties']['visibility']]
            return info

    def update_dependencies(self):
        '''
        Update bank dependencies

        :return: status of updates
        '''
        self.depends = []
        if self.run_depends:
            depends = self.get_dependencies()
        else:
            depends = []

        self.session.set('depends', {})
        res = True
        for dep in depends:
            self.session._session['depends'][dep] = False
        for dep in depends:
            if self.session._session['depends'][dep]:
                logging.debug('Update:Depends:' + dep + ':SKIP')
                # Bank has been marked as depends multiple times, run only once
                continue
            logging.info('Update:Depends:' + dep)
            b = Bank(dep)
            res = b.update()
            self.depends.append(b)
            self.session._session['depends'][dep] = res
            logging.info('Update:Depends:' + dep + ':' + str(res))
            if not res:
                break
        return res

    def get_bank(self, bank, no_log=False):
        '''
        Gets an other bank
        '''
        return Bank(bank, no_log=no_log)

    def get_dependencies(self, bank=None):
        '''
        Search all bank dependencies

        :return: list of bank names to update
        '''
        if bank is None:
            deps = self.config.get('depends')
        else:
            deps = bank.config.get('depends')
        if deps is None:
            return []
        # Mainn deps
        deps = deps.split(',')
        # Now search in deps if they themselves depend on other banks
        for dep in deps:
            b = Bank(dep)
            deps = b.get_dependencies() + deps
        return deps

    def is_owner(self):
        '''
        Checks if current user is owner or admin
        '''
        admin_config = self.config.get('admin')
        admin = []
        if admin_config is not None:
            admin = [x.strip() for x in admin_config.split(',')]
        if admin and os.environ['LOGNAME'] in admin:
            return True
        if os.environ['LOGNAME'] == self.bank['properties']['owner']:
            return True
        return False

    def set_owner(self, owner):
        '''
        Update bank owner, only if current owner
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.banks.update({'name': self.name}, {'$set': {'properties': {'owner': owner}}})

    def set_visibility(self, visibility):
        '''
        Update bank visibility, only if current owner
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.banks.update({'name': self.name}, {'$set': {'properties': {'visibility': visibility}}})

    def get_properties(self):
        '''
        Read bank properties from config file

        :return: properties dict
        '''

        owner = os.environ['LOGNAME']
        # If owner not set, use current user, else keep current
        if self.bank and 'properties' in self.bank and 'owner' in self.bank['properties']:
            owner = self.bank['properties']['owner']

        props = {
            'visibility': self.config.get('visibility.default'),
            'type': self.config.get('db.type').split(','),
            'tags': [],
            'owner': owner
        }

        return props

    @staticmethod
    def searchindex(query):
        return BmajIndex.searchq(query)

    @staticmethod
    def search(formats=None, types=None, with_sessions=True):
        '''
        Search all bank releases matching some formats and types

        Matches production release with at least one of formats and one of types
        '''
        if formats is None:
            formats = []

        if types is None:
            types = []

        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))
        searchfilter = {}
        if formats:
            searchfilter['production.formats'] = {'$in': formats}
        if with_sessions:
            res = MongoConnector.banks.find(searchfilter)
        else:
            res = MongoConnector.banks.find(searchfilter, {'sessions': 0})
        # Now search in which production release formats and types apply
        search_list = []
        for r in res:
            prod_to_delete = []
            for p in r['production']:
                is_format = False
                if not formats:
                    is_format = True
                # Are formats present in this production release?
                for f in formats:
                    if f in p['formats']:
                        is_format = True
                        break
                # Are types present in this production release?
                is_type = False
                if not types:
                    is_type = True
                if is_format:
                    for t in types:
                        if t in p['types'] or t in r['properties']['type']:
                            is_type = True
                            break
                if not is_type or not is_format:
                    prod_to_delete.append(p)
            for prod_del in prod_to_delete:
                r['production'].remove(prod_del)
            if len(r['production']) > 0:
                search_list.append(r)
        return search_list

    @staticmethod
    def list(with_sessions=False):
        '''
        Return a list of banks

        :param with_sessions: should sessions be returned or not (can be quite big)
        :type with_sessions: bool
        :return: list of :class:`biomaj.bank.Bank`
        '''
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        bank_list = []
        if with_sessions:
            res = MongoConnector.banks.find({})
        else:
            res = MongoConnector.banks.find({}, {'sessions': 0})
        for r in res:
            bank_list.append(r)
        return bank_list

    def controls(self):
        '''
        Initial controls (create directories etc...)
        '''
        data_dir = self.config.get('data.dir')
        bank_dir = self.config.get('dir.version')
        bank_dir = os.path.join(data_dir, bank_dir)
        if not os.path.exists(bank_dir):
            os.makedirs(bank_dir)

        offline_dir = self.config.get('offline.dir.name')
        offline_dir = os.path.join(data_dir, offline_dir)
        if not os.path.exists(offline_dir):
            os.makedirs(offline_dir)

        log_dir = self.config.get('log.dir')
        log_dir = os.path.join(log_dir, self.name)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def _delete(self):
        '''
        Delete bank from database, not files
        '''
        self.banks.remove({'_id': self.bank['_id']})

    def save_session(self):
        '''
        Save session in database
        '''
        self.session._session['last_update_time'] = time.time()
        self.session._session['log_file'] = self.config.log_file
        if self.use_last_session:
            # Remove last session
            self.banks.update({'name': self.name}, {'$pull': {'sessions': {'id': self.session._session['id']}}})
        # Insert session
        if self.session.get('action') == 'update':
            action = 'last_update_session'
        if self.session.get('action') == 'remove':
            action = 'last_remove_session'
        self.banks.update({'name': self.name}, {
            '$set': {
                action: self.session._session['id'],
                'properties': self.get_properties()
            },
            '$push': {'sessions': self.session._session}
        })
        BmajIndex.add(self.name, self.session._session)
        if self.session.get('action') == 'update' and not self.session.get_status(
                Workflow.FLOW_OVER) and self.session.get('release'):
            self.banks.update({'name': self.name},
                              {'$set': {'pending.' + self.session.get('release'): self.session._session['id']}})
        if self.session.get('action') == 'update' and self.session.get_status(Workflow.FLOW_OVER) and self.session.get(
                'update'):
            # We expect that a production release has reached the FLOW_OVER status.
            # If no update is needed (same release etc...), the *update* session of the session is set to False
            logging.debug('Bank:Save:' + self.name)
            if len(self.bank['production']) > 0:
                # Remove from database
                self.banks.update({'name': self.name},
                                  {'$pull': {'production': {'release': self.session._session['release']}}})
                # Update local object
                # index = 0
                # for prod in self.bank['production']:
                #  if prod['release'] == self.session._session['release']:
                #    break;
                #  index += 1
                # if index < len(self.bank['production']):
                #  self.bank['production'].pop(index)
            release_types = []
            for release_format in self.session._session['formats']:
                for release_files in self.session._session['formats'][release_format]:
                    if release_files['types']:
                        for rtype in release_files['types']:
                            if rtype not in release_types:
                                release_types.append(rtype)
            prod_dir = self.session.get_release_directory()
            if self.session.get('prod_dir'):
                prod_dir = self.session.get('prod_dir')
            production = {'release': self.session.get('release'),
                          'remoterelease': self.session.get('remoterelease'),
                          'session': self.session._session['id'],
                          'formats': list(self.session._session['formats'].keys()),
                          'types': release_types,
                          'size': self.session.get('fullsize'),
                          'data_dir': self.session._session['data_dir'],
                          'dir_version': self.session._session['dir_version'],
                          'prod_dir': prod_dir,
                          'freeze': False}
            self.bank['production'].append(production)

            self.banks.update({'name': self.name},
                              {'$push': {'production': production},
                               '$unset': {'pending.' + self.session.get('release'): ''}
                               })

            # self.banks.update({'name': self.name},
            #                  {'$unset': 'pending.'+self.session.get('release')
            #                  })

        self.bank = self.banks.find_one({'name': self.name})

    def clean_old_sessions(self):
        '''
        Delete old sessions, not latest ones nor related to production sessions
        '''
        if self.session is None:
            return
        # No previous session
        if 'sessions' not in self.bank:
            return
        # 'last_update_session' in self.bank and self.bank['last_update_session']
        old_sessions = []
        prod_releases = []
        for session in self.bank['sessions']:
            if session['id'] == self.session.get('id'):
                # Current session
                prod_releases.append(session['release'])
                continue
            if session['id'] == self.session.get('last_update_session'):
                prod_releases.append(session['release'])
                continue
            if session['id'] == self.session.get('last_remove_session'):
                continue
            is_prod_session = False
            for prod in self.bank['production']:
                if session['id'] == prod['session']:
                    is_prod_session = True
                    break
            if is_prod_session:
                prod_releases.append(session['release'])
                continue
            old_sessions.append(session)
        if len(old_sessions) > 0:
            for session in old_sessions:
                session_id = session['id']
                self.banks.update({'name': self.name}, {'$pull': {'sessions': {'id': session_id}}})
                if session['release'] not in prod_releases and session['release'] != self.session.get('release'):
                    # There might be unfinished releases linked to session, delete them
                    # if they are not related to a production directory or latest run
                    session_dir = os.path.join(self.config.get('data.dir'),
                                               self.config.get('dir.version'),
                                               self.name + '-' + str(session['release']))
                    if os.path.exists(session_dir):
                        logging.info('Bank:DeleteOldSessionDir:' + self.name + '-' + str(session['release']))
                        shutil.rmtree(session_dir)
            self.bank = self.banks.find_one({'name': self.name})

    def publish(self):
        '''
        Set session release to *current*
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        current_link = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'current')
        prod_dir = self.session.get_full_release_directory()

        to_dir = os.path.join(self.config.get('data.dir'),
                              self.config.get('dir.version'))

        if os.path.lexists(current_link):
            os.remove(current_link)
        os.chdir(to_dir)
        os.symlink(self.session.get_release_directory(), 'current')
        self.bank['current'] = self.session._session['id']
        self.banks.update({'name': self.name},
                          {
                              '$set': {'current': self.session._session['id']}
                          })

    def unpublish(self):
        '''
        Unset *current*
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        current_link = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'current')

        if os.path.lexists(current_link):
            os.remove(current_link)
        self.banks.update({'name': self.name},
                          {
                              '$set': {'current': None}
                          })

    def get_production(self, release):
        '''
        Get production field for release

        :param release: release name or production dir name
        :type release: str
        :return: production field
        '''
        production = None
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                production = prod
        return production

    def freeze(self, release):
        '''
        Freeze a production release

        When freezed, a production release cannot be removed (manually or automatically)

        :param release: release name or production dir name
        :type release: str
        :return: bool
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        rel = None
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                # Search session related to this production release
                rel = prod['release']
        if rel is None:
            logging.error('Release not found: ' + release)
        self.banks.update({'name': self.name, 'production.release': rel}, {'$set': {'production.$.freeze': True}})
        self.bank = self.banks.find_one({'name': self.name})
        return True

    def unfreeze(self, release):
        '''
        Unfreeze a production release to allow removal

        :param release: release name or production dir name
        :type release: str
        :return: bool
        '''
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        rel = None
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                # Search session related to this production release
                rel = prod['release']
        if rel is None:
            logging.error('Release not found: ' + release)
        self.banks.update({'name': self.name, 'production.release': rel}, {'$set': {'production.$.freeze': False}})
        self.bank = self.banks.find_one({'name': self.name})
        return True

    def get_new_session(self, flow=None):
        '''
        Returns an empty session

        :param flow: kind of workflow
        :type flow: :func:`biomaj.workflow.Workflow.FLOW`
        '''
        if flow is None:
            flow = Workflow.FLOW
        return Session(self.name, self.config, flow)

    def get_session_from_release(self, release):
        '''
        Loads the session matching a specific release

        :param release: release name oe production dir
        :type release: str
        :return: :class:`biomaj.session.Session`
        '''
        oldsession = None
        # Search production release matching release
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                # Search session related to this production release
                for s in self.bank['sessions']:
                    if s['id'] == prod['session']:
                        oldsession = s
                        break
                break
        if oldsession is None:
            # No prod session, try to find a session for this release, session may have failed or be stopped
            for s in self.bank['sessions']:
                if s['release'] and release.endswith(s['release']):
                    oldsession = s
        if oldsession is None:
            logging.error('No production session could be found for this release')
        return oldsession

    def load_session(self, flow=None, session=None):
        '''
        Loads last session or, if over or forced, a new session

        Creates a new session or load last session if not over

        :param flow: kind of workflow
        :type flow: :func:`biomaj.workflow.Workflow.FLOW`
        '''
        if flow is None:
            flow = Workflow.FLOW

        if session is not None:
            logging.debug('Load specified session ' + str(session['id']))
            self.session = Session(self.name, self.config, flow)
            self.session.load(session)
            self.use_last_session = True
            return
        if len(self.bank['sessions']) == 0 or self.options.get_option(Options.FROMSCRATCH):
            self.session = Session(self.name, self.config, flow)
            logging.debug('Start new session')
        else:
            # Take last session
            self.session = Session(self.name, self.config, flow)
            session_id = None
            # Load previous session for updates only
            if self.session.get('action') == 'update' and 'last_update_session' in self.bank and self.bank[
                'last_update_session']:
                session_id = self.bank['last_update_session']
                load_session = None
                for session in self.bank['sessions']:
                    if session['id'] == session_id:
                        load_session = session
                        break
                if load_session is not None:
                    # self.session.load(self.bank['sessions'][len(self.bank['sessions'])-1])
                    self.session.load(session)
                    # if self.config.last_modified > self.session.get('last_modified'):
                    #  # Config has changed, need to restart
                    #  self.session = Session(self.name, self.config, flow)
                    #  logging.info('Configuration file has been modified since last session, restart in any case a new session')
                    if self.session.get_status(Workflow.FLOW_OVER) and self.options.get_option(
                            Options.FROM_TASK) is None:
                        previous_release = self.session.get('remoterelease')
                        self.session = Session(self.name, self.config, flow)
                        self.session.set('previous_release', previous_release)
                        logging.debug('Start new session')
                    else:
                        logging.debug('Load previous session ' + str(self.session.get('id')))
                        self.use_last_session = True

    def remove_session(self, sid):
        '''
        Delete a session from db

        :param sid: id of the session
        :type sid: long
        :return: bool
        '''
        session_release = None
        _tmpbank = self.banks.find_one({'name': self.name})
        for s in _tmpbank['sessions']:
            if s['id'] == sid:
                session_release = s['release']
        if session_release is not None:
            self.banks.update({'name': self.name}, {'$pull': {
                'sessions': {'id': sid},
                'production': {'session': sid}
            },
                '$unset': {
                    'pending.' + session_release: ''
                }
            })
        else:
            self.banks.update({'name': self.name}, {'$pull': {
                'sessions': {'id': sid},
                'production': {'session': sid}
            }
            })
        # Update object
        self.bank = self.banks.find_one({'name': self.name})
        if session_release is not None:
            BmajIndex.remove(self.name, session_release)
        return True

    def get_data_dir(self):
        '''
        Returns bank data directory

        :return: str
        '''
        return os.path.join(self.config.get('data.dir'),
                            self.config.get('dir.version'))

    def removeAll(self, force=False):
        '''
        Remove all bank releases and database records

        :param force: force removal even if some production dirs are freezed
        :type force: bool
        :return: bool
        '''
        if not force:
            has_freeze = False
            for prod in self.bank['production']:
                if 'freeze' in prod and prod['freeze']:
                    has_freeze = True
                    break
            if has_freeze:
                logging.error('Cannot remove bank, some production directories are freezed, use force if needed')
                return False

        self.banks.remove({'name': self.name})
        BmajIndex.delete_all_bank(self.name)
        bank_data_dir = self.get_data_dir()
        logging.warn('DELETE ' + bank_data_dir)
        if os.path.exists(bank_data_dir):
            shutil.rmtree(bank_data_dir)
        bank_offline_dir = os.path.join(self.config.get('data.dir'), self.config.get('offline.dir.name'))
        if os.path.exists(bank_offline_dir):
            shutil.rmtree(bank_offline_dir)
        bank_log_dir = os.path.join(self.config.get('log.dir'), self.name)
        if os.path.exists(bank_log_dir) and self.no_log:
            shutil.rmtree(bank_log_dir)
        return True

    def get_status(self):
        '''
        Get status of current workflow

        :return: dict of current workflow status
        '''
        if self.bank['status'] is None:
            return {}
        return self.bank['status']

    def remove_pending(self, release):
        '''
        Remove pending releases

        :param release: release or release directory
        :type release: str
        :return: bool
        '''
        logging.warning('Bank:' + self.name + ':RemovePending')

        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        if not self.bank['pending']:
            return True
        pendings = self.bank['pending']
        for release in list(pendings.keys()):
            pending_session_id = pendings[release]
            pending_session = None
            for s in self.bank['sessions']:
                if s['id'] == pending_session_id:
                    pending_session = s
                    break
            session = Session(self.name, self.config, RemoveWorkflow.FLOW)
            if pending_session is None:
                session._session['release'] = release
            else:
                session.load(pending_session)
            if os.path.exists(session.get_full_release_directory()):
                logging.debug("Remove:Pending:Dir:" + session.get_full_release_directory())
                shutil.rmtree(session.get_full_release_directory())
            self.remove_session(pendings[release])
        self.banks.update({'name': self.name}, {'$set': {'pending': {}}})
        return True

    def remove(self, release):
        '''
        Remove a release (db and files)

        :param release: release or release directory
        :type release: str
        :return: bool
        '''
        logging.warning('Bank:' + self.name + ':Remove')

        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.session = self.get_new_session(RemoveWorkflow.FLOW)
        oldsession = None
        # Search production release matching release
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                if 'freeze' in prod and prod['freeze']:
                    logging.error('Cannot remove release, release is freezed, unfreeze it first')
                    return False
                # Search session related to this production release
                for s in self.bank['sessions']:
                    if s['id'] == prod['session']:
                        oldsession = s
                        break
                break
        if oldsession is None:
            logging.error('No production session could be found for this release')
            return False
        if 'current' in self.bank and self.bank['current'] == oldsession['id']:
            logging.error('This release is the release in the main release production, you should first unpublish it')
            return False

        # New empty session for removal
        session = Session(self.name, self.config, RemoveWorkflow.FLOW)
        session.set('action', 'remove')
        session.set('release', oldsession['release'])
        session.set('update_session_id', oldsession['id'])
        self.session = session
        # Reset status, we take an update session
        res = self.start_remove(session)
        self.save_session()

        return res

    def update(self, depends=False):
        '''
        Launch a bank update

        :param depends: run update of bank dependencies first
        :type depends: bool
        :return: bool
        '''
        logging.warning('Bank:' + self.name + ':Update')

        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.run_depends = depends

        self.controls()
        if self.options.get_option('release'):
            logging.info('Bank:' + self.name + ':Release:' + self.options.get_option('release'))
            s = self.get_session_from_release(self.options.get_option('release'))
            # No session in prod
            if s is None:
                logging.error('Release does not exists: ' + self.options.get_option('release'))
                return False
            self.load_session(UpdateWorkflow.FLOW, s)
        else:
            logging.info('Bank:' + self.name + ':Release:latest')
            self.load_session(UpdateWorkflow.FLOW)
        # if from task, reset workflow status in session.
        if self.options.get_option('from_task'):
            set_to_false = False
            for task in self.session.flow:
                # If task was in False status (KO) and we ask to start after this task, exit
                if not set_to_false and not self.session.get_status(task['name']) and task[
                    'name'] != self.options.get_option('from_task'):
                    logging.error(
                        'Previous task ' + task['name'] + ' was not successful, cannot restart after this task')
                    return False
                if task['name'] == self.options.get_option('from_task'):
                    set_to_false = True
                if set_to_false:
                    # After from_task task, tasks must be set to False to be run
                    self.session.set_status(task['name'], False)
                    proc = None
                    if task['name'] in [Workflow.FLOW_POSTPROCESS, Workflow.FLOW_PREPROCESS,
                                        Workflow.FLOW_REMOVEPROCESS]:
                        proc = self.options.get_option('process')
                        self.session.reset_proc(task['name'], proc)
                        # if task['name'] == Workflow.FLOW_POSTPROCESS:
                        #  self.session.reset_proc(Workflow.FLOW_POSTPROCESS, proc)
                        # elif task['name'] == Workflow.FLOW_PREPROCESS:
                        #  self.session.reset_proc(Workflow.FLOW_PREPROCESS, proc)
                        # elif task['name'] == Workflow.FLOW_REMOVEPROCESS:
                        #  self.session.reset_proc(Workflow.FLOW_REMOVEPROCESS, proc)
        self.session.set('action', 'update')
        res = self.start_update()
        self.save_session()
        return res

    def start_remove(self, session):
        '''
        Start a removal workflow

        :param session: Session to remove
        :type session: :class:`biomaj.session.Session`
        :return: bool
        '''
        workflow = RemoveWorkflow(self, session)
        return workflow.start()

    def start_update(self):
        '''
        Start an update workflow
        '''
        workflow = UpdateWorkflow(self)
        return workflow.start()
