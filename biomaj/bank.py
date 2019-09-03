from builtins import str
from builtins import object
import os
import logging
import time
import shutil
import json
from datetime import datetime

import redis

from biomaj.mongo_connector import MongoConnector
from biomaj.session import Session
from biomaj.workflow import UpdateWorkflow
from biomaj.workflow import RemoveWorkflow
from biomaj.workflow import RepairWorkflow
from biomaj.workflow import Workflow
from biomaj.workflow import ReleaseCheckWorkflow
from biomaj_core.config import BiomajConfig
from biomaj.options import Options
from biomaj.process.processfactory import ProcessFactory
from biomaj_core.bmajindex import BmajIndex

import getpass


class Bank(object):
    """
    BioMAJ bank
    """

    def __init__(self, name, options=None, no_log=False):
        """
        Get a bank from db or creates a new one

        :param name: name of the bank, must match its config file
        :type name: str
        :param options: bank options
        :type options: argparse
        :param no_log: create a log file for the bank
        :type no_log: bool
        """
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
        self.history = MongoConnector.history
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
        """
        Checks bank configuration
        """
        return self.config.check()

    def is_locked(self):
        """
        Checks if bank is locked ie action is in progress
        """
        data_dir = self.config.get('data.dir')
        lock_dir = self.config.get('lock.dir', default=data_dir)
        lock_file = os.path.join(lock_dir, self.name + '.lock')
        if os.path.exists(lock_file):
            return True
        else:
            return False

    @staticmethod
    def get_history(limit=100):
        """
        Get list of bank update/remove operations
        """
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        hist_list = []
        hist = MongoConnector.history.find({}).sort("start", -1).limit(limit)
        for h in hist:
            del h['_id']
            hist_list.append(h)
        return hist_list

    @staticmethod
    def get_banks_disk_usage():
        """
        Get disk usage per bank and release
        """
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
        """
        Get release info for the bank. Used with --status option from biomaj-cly.py
        :param full: Display full for the bank
        :type full: Boolean
        :return: Dict with keys
                      if full=True
                           - info, prod, pend
                      else
                           - info
        """

        _bank = self.bank
        info = {}
        release = 'N/A'
        last_update = 'N/A'
        if 'last_update_session' in _bank:
            last_update = datetime.fromtimestamp(_bank['last_update_session']).strftime("%Y-%m-%d %H:%M:%S")

        if full:
            bank_info = []
            prod_info = []
            pend_info = []

            if 'current' in _bank and _bank['current']:
                for prod in _bank['production']:
                    if _bank['current'] == prod['session']:
                        release = prod['release']
            # Bank info header
            bank_info.append(["Name", "Type(s)", "Last update status", "Published release"])
            bank_info.append([_bank['name'],
                              str(','.join(_bank['properties']['type'])),
                              str(last_update),
                              str(release)])
            # Bank production info header
            prod_info.append(["Session", "Remote release", "Release", "Directory", "Freeze", "Format(s)"])
            for prod in _bank['production']:
                data_dir = self.config.get('data.dir')
                dir_version = self.config.get('dir.version')
                if 'data.dir' in prod:
                    data_dir = prod['data.dir']
                if 'dir.version' in prod:
                    dir_version = prod['dir.version']
                if not prod['prod_dir'] or not dir_version or not data_dir:
                    continue
                release_dir = os.path.join(data_dir,
                                           dir_version,
                                           prod['prod_dir'])
                date = datetime.fromtimestamp(prod['session']).strftime('%Y-%m-%d %H:%M:%S')
                formats = ""
                # Check the value exist , is not empty, and a list.
                if 'formats' in prod and prod['formats'] and isinstance(prod['formats'], list):
                    formats = str(','.join(prod['formats']))
                prod_info.append([date,
                                  prod['remoterelease'],
                                  prod['release'],
                                  release_dir,
                                  'yes' if 'freeze' in prod and prod['freeze'] else 'no',
                                  formats])
            # Bank pending info header
            if 'pending' in _bank and len(_bank['pending']) > 0:
                pend_info.append(["Pending release", "Last run"])
                for pending in _bank['pending']:
                    run = ""
                    try:
                        run = datetime.fromtimestamp(pending['id']).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logging.error('BANK:ERROR:invalid pending id: ' + str(pending['id']))
                        logging.error('BANK:ERROR:invalid pending id: ' + str(e))
                    pend_info.append([pending['release'], run])

            info['info'] = bank_info
            info['prod'] = prod_info
            info['pend'] = pend_info
            return info

        else:
            if 'current' in _bank and _bank['current']:
                for prod in _bank['production']:
                    if _bank['current'] == prod['session']:
                        release = prod['remoterelease']
            info['info'] = [_bank['name'], ','.join(_bank['properties']['type']),
                            str(release), _bank['properties']['visibility'], last_update]
            return info

    def update_dependencies(self):
        """
        Update bank dependencies

        :return: status of updates
        """
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
            if self.options and hasattr(self.options, 'user') and self.options.user:
                b.options.user = self.options.user
            res = b.update()
            self.depends.append(b)
            self.session._session['depends'][dep] = res
            logging.info('Update:Depends:' + dep + ':' + str(res))
            if not res:
                break
        if depends:
            # Revert logging config
            self.config.reset_logger()
        return res

    def get_bank(self, bank=None, no_log=False):
        """
        Gets an other bank
        """
        if bank is None:
            return self.bank
        return Bank(bank, no_log=no_log)

    def get_dependencies(self, bank=None):
        """
        Search all bank dependencies

        :return: list of bank names to update
        """
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
            sub_options = None
            if self.options and hasattr(self.options, 'user') and self.options.user:
                sub_options = Options()
                sub_options.user = self.options.user
            b = Bank(dep, options=sub_options, no_log=True)
            deps = b.get_dependencies() + deps
        return deps

    def is_owner(self):
        """
        Checks if current user is owner or admin
        """
        owner = getpass.getuser()
        admin_config = self.config.get('admin')
        admin = []
        if admin_config is not None:
            admin = [x.strip() for x in admin_config.split(',')]

        current_user = None
        if self.config.get('micro.biomaj.service.daemon', default=None) == '1':
            if self.options and hasattr(self.options, 'user') and self.options.user:
                current_user = self.options.user
            else:
                logging.debug('Micro services activated but user not authenticated')
                return False
        else:
            current_user = owner

        if admin and current_user in admin:
            return True
        if current_user == self.bank['properties']['owner']:
            return True
        return False

    def set_owner(self, owner):
        """
        Update bank owner, only if current owner
        """
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.banks.update({'name': self.name}, {'$set': {'properties.owner': owner}})

    def set_visibility(self, visibility):
        """
        Update bank visibility, only if current owner
        """
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.banks.update({'name': self.name}, {'$set': {'properties.visibility': visibility}})

    def get_properties(self):
        """
        Read bank properties from config file

        :return: properties dict
        """
        owner = None
        if self.config.get('micro.biomaj.service.daemon', default=None) == '1':
            if self.options and hasattr(self.options, 'user') and self.options.user:
                owner = self.options.user
            else:
                logging.debug('Micro services activated but user not authenticated')
                raise Exception('Micro services activated but user not authenticated')
        else:
            owner = getpass.getuser()

        # If owner not set, use current user, else keep current
        if self.bank and 'properties' in self.bank and 'owner' in self.bank['properties']:
            owner = self.bank['properties']['owner']

        props = {
            'visibility': self.config.get('visibility.default'),
            'type': self.config.get('db.type').split(','),
            'tags': [],
            'owner': owner,
            'desc': self.config.get('db.fullname')
        }

        return props

    @staticmethod
    def user_banks(user_name):
        """
        Get user banks name
        :param user_name: user identifier
        :type user_name: str
        :return: list of bank name
        """
        banks = MongoConnector.banks.find({'properties.owner': user_name}, {'name': 1})
        return banks

    @staticmethod
    def searchindex(query):
        return BmajIndex.searchq(query)

    @staticmethod
    def search(formats=None, types=None, with_sessions=True):
        """
        Search all bank releases matching some formats and types

        Matches production release with at least one of formats and one of types
        """
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
        """
        Return a list of banks

        :param with_sessions: should sessions be returned or not (can be quite big)
        :type with_sessions: bool
        :return: list of :class:`biomaj.bank.Bank`
        """
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
        """
        Initial controls (create directories etc...)
        """
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
        """
        Delete bank from database, not files
        """
        self.banks.remove({'_id': self.bank['_id']})

    def save_session(self):
        """
        Save session in database
        """
        self.session._session['last_update_time'] = time.time()
        self.session._session['log_file'] = self.config.log_file
        if self.use_last_session:
            # Remove last session
            self.banks.update({'name': self.name}, {'$pull': {'sessions': {'id': self.session._session['id']}}})
        # Insert session
        if self.session.get('action') == 'update':
            action = 'last_update_session'
        elif self.session.get('action') == 'remove':
            action = 'last_remove_session'
        else:
            action = 'last_update_session'

        cache_dir = self.config.get('cache.dir')
        download_files = self.session.get('download_files')
        if download_files is not None:
            f_downloaded_files = open(os.path.join(cache_dir, 'files_' + str(self.session.get('id'))), 'w')
            f_downloaded_files.write(json.dumps(download_files))
            f_downloaded_files.close()
            self.session.set('download_files', [])

        local_files = self.session.get('files')
        if local_files is not None:
            f_local_files = open(os.path.join(cache_dir, 'local_files_' + str(self.session.get('id'))), 'w')
            f_local_files.write(json.dumps(download_files))
            f_local_files.close()
            self.session.set('files', [])

        self.banks.update({'name': self.name}, {
            '$set': {
                action: self.session._session['id'],
                'properties': self.get_properties()
            },
            '$push': {'sessions': self.session._session}
        })
        BmajIndex.add(self.name, self.session._session)
        if self.session.get('action') == 'update' and not self.session.get_status(Workflow.FLOW_OVER)\
                and self.session.get('release'):
            release = self.session.get('release')
            found = self.banks.find_one({'name': self.name, 'pending.release': release})
            if found is None:
                self.banks.update({'name': self.name},
                                  {'$push': {'pending': {'release': self.session.get('release'),
                                                         'id': self.session._session['id']}}})

        if self.session.get('action') == 'update' and self.session.get_status(Workflow.FLOW_OVER) and self.session.get(
                'update'):
            # We expect that a production release has reached the FLOW_OVER status.
            # If no update is needed (same release etc...), the *update* session of the session is set to False
            logging.debug('Bank:Save:' + self.name)
            if len(self.bank['production']) > 0:
                # Remove from database
                self.banks.update({'name': self.name},
                                  {'$pull': {'production': {'release': self.session._session['release']}}})

            release_types = []
            if self.config.get('db.type'):
                release_types = self.config.get('db.type').split(',')
            release_formats = list(self.session._session['formats'].keys())
            if self.config.get('db.formats'):
                config_formats = self.config.get('db.formats').split(',')
                for config_format in config_formats:
                    if config_format not in release_formats:
                        release_formats.append(config_format)

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
                          'formats': release_formats,
                          'types': release_types,
                          'size': self.session.get('fullsize'),
                          'data_dir': self.session._session['data_dir'],
                          'dir_version': self.session._session['dir_version'],
                          'prod_dir': prod_dir,
                          'freeze': False}
            self.bank['production'].append(production)
            self.banks.update({'name': self.name},
                              {
                              '$push': {'production': production}
                              })
            self.banks.update({'name': self.name},
                              {
                              '$pull': {
                                  'pending': {
                                      'release': self.session.get('release'),
                                      'id': self.session._session['id']
                                  }
                              }
                              })

        self.bank = self.banks.find_one({'name': self.name})

    def clean_old_sessions(self):
        """
        Delete old sessions, not latest ones nor related to production sessions
        """
        if self.session is None:
            return
        # No previous session
        if 'sessions' not in self.bank:
            return
        if self.config.get_bool('keep.old.sessions'):
            logging.debug('keep old sessions, skipping...')
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
                # Check if in pending sessions
                if 'pending' in self.bank:
                    for rel in self.bank['pending']:
                        rel_session = rel['id']
                        if rel_session == session_id:
                            self.banks.update({'name': self.name},
                                              {'$pull': {'pending': {'release': session['release'], 'id': session_id}}})
                if session['release'] not in prod_releases and session['release'] != self.session.get('release'):
                    # There might be unfinished releases linked to session, delete them
                    # if they are not related to a production directory or latest run
                    session_dir = os.path.join(self.config.get('data.dir'),
                                               self.config.get('dir.version'),
                                               self.name + self.config.get('release.separator', default='_') + str(session['release']))
                    if os.path.exists(session_dir):
                        logging.info('Bank:DeleteOldSessionDir:' + self.name + self.config.get('release.separator', default='_') + str(session['release']))
                        shutil.rmtree(session_dir)
            self.bank = self.banks.find_one({'name': self.name})

    def publish(self):
        """
        Set session release to *current*
        """
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        current_link = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'current')

        to_dir = os.path.join(self.config.get('data.dir'),
                              self.config.get('dir.version'))

        if os.path.lexists(current_link):
            os.remove(current_link)
        os.chdir(to_dir)
        os.symlink(self.session.get_release_directory(), 'current')
        self.bank['current'] = self.session._session['id']
        self.banks.update(
            {'name': self.name},
            {'$set': {'current': self.session._session['id']}}
        )

        release_file = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'RELEASE.txt')

        with open(release_file, 'w') as outfile:
            outfile.write('Bank: %s\nRelease: %s\nRemote release:%s\n' % (self.name, self.session.get('release'), self.session.get('remoterelease')))

    def unpublish(self):
        """
        Unset *current*
        """
        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        current_link = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'current')

        if os.path.lexists(current_link):
            os.remove(current_link)

        release_file = os.path.join(self.config.get('data.dir'),
                                    self.config.get('dir.version'),
                                    'RELEASE.txt')
        if os.path.exists(release_file):
            os.remove(release_file)

        self.banks.update(
            {'name': self.name},
            {'$set': {'current': None}}
        )

    def get_production(self, release):
        """
        Get production field for release

        :param release: release name or production dir name
        :type release: str
        :return: production field
        """
        release = str(release)
        production = None
        for prod in self.bank['production']:
            if prod['release'] == release or prod['prod_dir'] == release:
                production = prod
        return production

    def freeze(self, release):
        """
        Freeze a production release

        When freezed, a production release cannot be removed (manually or automatically)

        :param release: release name or production dir name
        :type release: str
        :return: bool
        """
        release = str(release)
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
        """
        Unfreeze a production release to allow removal

        :param release: release name or production dir name
        :type release: str
        :return: bool
        """
        release = str(release)
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
        """
        Returns an empty session

        :param flow: kind of workflow
        :type flow: :func:`biomaj.workflow.Workflow.FLOW`
        """
        if flow is None:
            flow = Workflow.FLOW
        return Session(self.name, self.config, flow)

    def get_session_from_release(self, release):
        """
        Loads the session matching a specific release

        :param release: release name oe production dir
        :type release: str
        :return: :class:`biomaj.session.Session`
        """
        release = str(release)
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
        """
        Loads last session or, if over or forced, a new session

        Creates a new session or load last session if not over

        :param flow: kind of workflow
        :type flow: :func:`biomaj.workflow.Workflow.FLOW`
        """
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
        """
        Delete a session from db

        :param sid: id of the session
        :type sid: long
        :return: bool
        """
        session_release = None
        _tmpbank = self.banks.find_one({'name': self.name})
        for s in _tmpbank['sessions']:
            if s['id'] == sid:
                session_release = s['release']

        cache_dir = self.config.get('cache.dir')
        download_files = os.path.join(cache_dir, 'files_' + str(sid))
        if os.path.exists(download_files):
            os.remove(download_files)

        local_files = os.path.join(cache_dir, 'local_files_' + str(sid))
        if os.path.exists(local_files):
            os.remove(local_files)

        if self.config.get_bool('keep.old.sessions'):
            logging.debug('keep old sessions')
            if session_release is not None:
                self.banks.update({'name': self.name}, {
                    '$pull': {
                        'production': {'session': sid},
                        'pending': {
                            'release': session_release,
                            'id': sid
                        }
                    }
                })
            else:
                self.banks.update({'name': self.name}, {'$pull': {
                    'production': {'session': sid}
                }
                })
            self.banks.update({'name': self.name, 'sessions.id': sid},
                              {'$set': {'sessions.$.deleted': time.time()}})
        else:
            if session_release is not None:
                self.banks.update({'name': self.name}, {'$pull': {
                    'sessions': {'id': sid},
                    'production': {'session': sid},
                    'pending': {'release': session_release,
                                'id': sid}
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
        """
        Returns bank data directory

        :return: str
        """
        return os.path.join(self.config.get('data.dir'),
                            self.config.get('dir.version'))

    def removeAll(self, force=False):
        """
        Remove all bank releases and database records

        :param force: force removal even if some production dirs are freezed
        :type force: bool
        :return: bool
        """
        start_time = datetime.now()
        start_time = time.mktime(start_time.timetuple())
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
            try:
                shutil.rmtree(bank_data_dir)
            except Exception:
                logging.exception('Failed to delete bank directory: ' + bank_data_dir)
                logging.error('Bank will be deleted but some files/dirs may still be present on system, you can safely manually delete them')
        bank_offline_dir = os.path.join(self.config.get('data.dir'), self.config.get('offline.dir.name'))
        if os.path.exists(bank_offline_dir):
            try:
                shutil.rmtree(bank_offline_dir)
            except Exception:
                logging.exception('Failed to delete bank offline directory: ' + bank_offline_dir)
                logging.error('Bank will be deleted but some files/dirs may still be present on system, you can safely manually delete them')
        bank_log_dir = os.path.join(self.config.get('log.dir'), self.name)
        if os.path.exists(bank_log_dir) and self.no_log:
            try:
                shutil.rmtree(bank_log_dir)
            except Exception:
                logging.exception('Failed to delete bank log directory: ' + bank_log_dir)
                logging.error('Bank will be deleted but some files/dirs may still be present on system, you can safely manually delete them')
        end_time = datetime.now()
        end_time = time.mktime(end_time.timetuple())
        self.history.insert({
            'bank': self.name,
            'error': False,
            'start': start_time,
            'end': end_time,
            'action': 'remove',
            'updated': None
        })
        return True

    def get_status(self):
        """
        Get status of current workflow

        :return: dict of current workflow status
        """
        if 'status' not in self.bank or self.bank['status'] is None:
            return {}
        return self.bank['status']

    def remove_pending(self, release=None):
        """
        Remove pending releases if 'release is None

        :param release: release or release directory, default None
        :type release: str
        :return: bool
        """
        if release:
            release = str(release)
        logging.warning('Bank:' + self.name + ':RemovePending')

        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        if 'pending' not in self.bank:
            return True
        pendings = self.bank['pending']
        last_update = None
        if 'last_update_session' in self.bank:
            last_update = self.bank['last_update_session']

        for pending in pendings:
            # Only work with pending for argument release
            if release and release != pending['release']:
                continue
            pending_session_id = pending['id']
            pending_session = None
            for s in self.bank['sessions']:
                if s['id'] == pending_session_id:
                    pending_session = s
                    break
            session = Session(self.name, self.config, RemoveWorkflow.FLOW)
            if pending_session is None:
                session._session['release'] = pending['release']
            else:
                session.load(pending_session)
            if os.path.exists(session.get_full_release_directory()):
                logging.debug("Remove:Pending:Dir:" + session.get_full_release_directory())
                shutil.rmtree(session.get_full_release_directory())
            self.remove_session(pending['id'])
            if last_update and last_update == pending_session_id:
                self.banks.update({'name': self.name},
                                  {'$unset': {'last_update_session': ''}})

        # If no release ask for deletion, remove all pending
        if not release:
            self.banks.update({'name': self.name}, {'$set': {'pending': []}})
        return True

    def remove(self, release):
        """
        Remove a release (db and files)

        :param release: release or release directory
        :type release: str
        :return: bool
        """
        release = str(release)
        logging.warning('Bank:' + self.name + ':Remove')
        start_time = datetime.now()
        start_time = time.mktime(start_time.timetuple())

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
        self.session.set('workflow_status', res)
        self.save_session()
        end_time = datetime.now()
        end_time = time.mktime(end_time.timetuple())
        self.history.insert({
            'bank': self.name,
            'error': not res,
            'start': start_time,
            'end': end_time,
            'action': 'remove',
            'updated': None
        })

        return res

    def repair(self):
        """
        Launch a bank repair

        :return: bool
        """
        logging.warning('Bank:' + self.name + ':Repair')
        start_time = datetime.now()
        start_time = time.mktime(start_time.timetuple())

        if not self.is_owner():
            logging.error('Not authorized, bank owned by ' + self.bank['properties']['owner'])
            raise Exception('Not authorized, bank owned by ' + self.bank['properties']['owner'])

        self.run_depends = False

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
        self.session.set('action', 'update')
        res = self.start_repair()
        self.session.set('workflow_status', res)
        self.save_session()
        try:
            self.__stats()
        except Exception:
            logging.exception('Failed to send stats')
        end_time = datetime.now()
        end_time = time.mktime(end_time.timetuple())
        self.history.insert({
            'bank': self.name,
            'error': not res,
            'start': start_time,
            'end': end_time,
            'action': 'repair',
            'updated': self.session.get('update')
        })
        return res

    def start_repair(self):
        """
        Start an repair workflow
        """
        workflow = RepairWorkflow(self)
        if self.options and self.options.get_option('redis_host'):
            redis_client = redis.StrictRedis(
                host=self.options.get_option('redis_host'),
                port=self.options.get_option('redis_port'),
                db=self.options.get_option('redis_db'),
                decode_responses=True
            )
            workflow.redis_client = redis_client
            workflow.redis_prefix = self.options.get_option('redis_prefix')
            if redis_client.get(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel'):
                logging.warn('Cancel requested, stopping update')
                redis_client.delete(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel')
                return False
        return workflow.start()

    def update(self, depends=False):
        """
        Launch a bank update

        :param depends: run update of bank dependencies first
        :type depends: bool
        :return: bool
        """
        logging.warning('Bank:' + self.name + ':Update')
        start_time = datetime.now()
        start_time = time.mktime(start_time.timetuple())

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
                if not set_to_false and not self.session.get_status(task['name']) and \
                        task['name'] != self.options.get_option('from_task'):
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
                        reset = self.session.reset_proc(task['name'], proc)
                        if not reset:
                            logging.info("Process %s not found in %s" % (str(proc), task['name']))
                            return False
            if not set_to_false:
                logging.error('No task found named %s' % (self.options.get_option('from_task')))
                return False
        self.session.set('action', 'update')
        res = self.start_update()
        self.session.set('workflow_status', res)
        self.save_session()
        try:
            self.__stats()
        except Exception:
            logging.exception('Failed to send stats')
        end_time = datetime.now()
        end_time = time.mktime(end_time.timetuple())
        self.history.insert({
            'bank': self.name,
            'error': not res,
            'start': start_time,
            'end': end_time,
            'action': 'update',
            'updated': self.session.get('update')
        })
        return res

    def __stats(self):
        '''
        Send stats to Influxdb if enabled
        '''
        try:
            from influxdb import InfluxDBClient
        except Exception as e:
            logging.error('Cannot load influxdb library' + str(e))
            return
        db_host = self.config.get('influxdb.host', default=None)
        if not db_host:
            return
        if not self.session.get_status(Workflow.FLOW_OVER):
            return
        if 'stats' not in self.session._session:
            return

        db_port = int(self.config.get('influxdb.port', default='8086'))
        db_user = self.config.get('influxdb.user', default=None)
        db_password = self.config.get('influxdb.password', default=None)
        db_name = self.config.get('influxdb.db', default='biomaj')
        influxdb = None
        try:
            if db_user and db_password:
                influxdb = InfluxDBClient(host=db_host, port=db_port, username=db_user, password=db_password, database=db_name)
            else:
                influxdb = InfluxDBClient(host=db_host, port=db_port, database=db_name)
        except Exception as e:
            logging.error('Failed to connect to InfluxDB, database may not be created, skipping the record of statistics')
            logging.exception('InfluxDB connection error: ' + str(e))
            return
        metrics = []

        if 'production' not in self.bank or not self.bank['production']:
            return

        productions = self.bank['production']
        total_size = 0
        latest_size = 0
        if not productions:
            return
        for production in productions:
            if 'size' in production:
                total_size += production['size']

        influx_metric = {
            "measurement": 'biomaj.production.size.total',
            "fields": {
                "value": float(total_size)
            },
            "tags": {
                "bank": self.name
            }
        }
        metrics.append(influx_metric)

        all_banks = Bank.list()
        nb_banks_with_prod = 0
        if all_banks:
            for bank_info in all_banks:
                if 'production' in bank_info and len(bank_info['production']) > 0:
                    nb_banks_with_prod += 1
            influx_metric = {
                "measurement": 'biomaj.banks.quantity',
                "fields": {
                    "value": nb_banks_with_prod
                }
            }
            metrics.append(influx_metric)

        workflow_duration = 0
        for flow in list(self.session._session['stats']['workflow'].keys()):
            workflow_duration += self.session._session['stats']['workflow'][flow]

        influx_metric = {
            "measurement": 'biomaj.workflow.duration',
            "fields": {
                "value": workflow_duration
            },
            "tags": {
                "bank": self.name
            }
        }
        metrics.append(influx_metric)

        if self.session.get('update'):
            latest_size = self.session.get('fullsize')
            influx_metric = {
                "measurement": 'biomaj.production.size.latest',
                "fields": {
                    "value": float(latest_size)
                },
                "tags": {
                    "bank": self.name
                }
            }
            metrics.append(influx_metric)

            influx_metric = {
                "measurement": 'biomaj.bank.update.downloaded_files',
                "fields": {
                    "value": self.session._session['stats']['nb_downloaded_files']
                },
                "tags": {
                    "bank": self.name
                }
            }
            metrics.append(influx_metric)

            influx_metric = {
                "measurement": 'biomaj.bank.update.new',
                "fields": {
                    "value": 1
                },
                "tags": {
                    "bank": self.name
                }
            }
            metrics.append(influx_metric)

        res = None
        try:
            res = influxdb.write_points(metrics, time_precision="s")
        except Exception as e:
            logging.error('Failed to connect to InfluxDB, database may not be created, skipping the record of statistics')
            logging.exception('InfluxDB connection error: ' + str(e))
            return

        if not res:
            logging.error('Failed to send metrics to database')

    def check_remote_release(self):
        '''
        Check remote release of the bank
        '''
        logging.warning('Bank:' + self.name + ':Check remote release')
        self.controls()
        logging.info('Bank:' + self.name + ':Release:latest')
        self.load_session(ReleaseCheckWorkflow.FLOW)
        workflow = ReleaseCheckWorkflow(self)
        res = workflow.start()
        remoterelease = None
        if res:
            remoterelease = workflow.session.get('remoterelease')
        return (res, remoterelease)

    def start_remove(self, session):
        """
        Start a removal workflow

        :param session: Session to remove
        :type session: :class:`biomaj.session.Session`
        :return: bool
        """
        workflow = RemoveWorkflow(self, session)
        if self.options and self.options.get_option('redis_host'):
            redis_client = redis.StrictRedis(
                host=self.options.get_option('redis_host'),
                port=self.options.get_option('redis_port'),
                db=self.options.get_option('redis_db'),
                decode_responses=True
            )
            workflow.redis_client = redis_client
            workflow.redis_prefix = self.options.get_option('redis_prefix')
            if redis_client.get(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel'):
                logging.warn('Cancel requested, stopping update')
                redis_client.delete(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel')
                return False
        return workflow.start()

    def start_update(self):
        """
        Start an update workflow
        """
        workflow = UpdateWorkflow(self)
        if self.options and self.options.get_option('redis_host'):
            redis_client = redis.StrictRedis(
                host=self.options.get_option('redis_host'),
                port=self.options.get_option('redis_port'),
                db=self.options.get_option('redis_db'),
                decode_responses=True
            )
            workflow.redis_client = redis_client
            workflow.redis_prefix = self.options.get_option('redis_prefix')
            if redis_client.get(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel'):
                logging.warn('Cancel requested, stopping update')
                redis_client.delete(self.options.get_option('redis_prefix') + ':' + self.name + ':action:cancel')
                return False
        return workflow.start()
