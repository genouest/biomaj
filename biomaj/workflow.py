from builtins import str
from builtins import range
from builtins import object
import logging
import datetime
import time
import os
import shutil
import tempfile
import re
import traceback
import json
import hashlib
import sys

from biomaj_core.utils import Utils
from biomaj_download.downloadclient import DownloadClient
from biomaj_download.message import downmessage_pb2
from biomaj_download.download.curl import HTTPParse
from biomaj_download.download.localcopy import LocalDownload

from biomaj.mongo_connector import MongoConnector
from biomaj.options import Options
from biomaj.process.processfactory import RemoveProcessFactory, PreProcessFactory, PostProcessFactory

from biomaj_zipkin.zipkin import Zipkin
from yapsy.PluginManager import PluginManager


class Workflow(object):
    """
    Bank update workflow
    """

    FLOW_INIT = 'init'
    FLOW_CHECK = 'check'
    FLOW_DEPENDS = 'depends'
    FLOW_PREPROCESS = 'preprocess'
    FLOW_RELEASE = 'release'
    FLOW_DOWNLOAD = 'download'
    FLOW_POSTPROCESS = 'postprocess'
    FLOW_REMOVEPROCESS = 'removeprocess'
    FLOW_PUBLISH = 'publish'
    FLOW_OVER = 'over'

    FLOW = [
        {'name': 'init', 'steps': []},
        {'name': 'check', 'steps': []},
        {'name': 'over', 'steps': []}
    ]

    def __init__(self, bank, session=None):
        """
        Instantiate a new workflow

        :param bank: bank on which to apply the workflow
        :type bank: :class:`biomaj.bank.Bank`
        """
        self.bank = bank
        if session is None:
            self.session = bank.session
        else:
            self.session = session
            self.bank.session = session
        self.options = bank.options
        self.name = bank.name
        # Skip all remaining tasks, no need to update
        self.skip_all = False

        self.session._session['update'] = False
        self.session._session['remove'] = False
        self.session.config.set('localrelease', '')
        self.session.config.set('remoterelease', '')
        # For micro services
        self.redis_client = None
        self.redis_prefix = None
        # Zipkin
        self.span = None

    def get_flow(self, task):
        for flow in Workflow.FLOW:
            if flow['name'] == task:
                return flow

    def start(self):
        """
        Start the workflow
        """
        logging.info('Workflow:Start')
        if 'stats' not in self.session._session:
            self.session._session['stats'] = {
                'workflow': {},
                'nb_downloaded_files': 0
            }

        for flow in self.session.flow:
            dt = datetime.datetime.now()
            start_timestamp = time.mktime(dt.timetuple())
            if self.skip_all:
                logging.info('Workflow:Skip:' + flow['name'])
                self.session._session['status'][flow['name']] = None
                self.session._session['status'][Workflow.FLOW_OVER] = True
                continue

            if self.options.get_option(Options.STOP_BEFORE) == flow['name']:
                self.wf_over()
                break

            # Check for cancel request
            if self.redis_client and self.redis_client.get(self.redis_prefix + ':' + self.bank.name + ':action:cancel'):
                logging.warn('Cancel requested, stopping update')
                self.redis_client.delete(self.redis_prefix + ':' + self.bank.name + ':action:cancel')
                self.wf_over()
                return False

            # Always run INIT
            if flow['name'] != Workflow.FLOW_INIT and self.session.get_status(flow['name']):
                logging.info('Workflow:Skip:' + flow['name'])
            if flow['name'] == Workflow.FLOW_INIT or not self.session.get_status(flow['name']):
                logging.info('Workflow:Start:' + flow['name'])
                span = None
                if self.options.get_option('traceId'):
                    trace_id = self.options.get_option('traceId')
                    span_id = self.options.get_option('spanId')
                    span = Zipkin('biomaj-workflow', flow['name'], trace_id=trace_id, parent_id=span_id)
                    self.span = span
                    self.bank.config.set('zipkin_trace_id', span.get_trace_id())
                    self.bank.config.set('zipkin_span_id', span.get_span_id())

                try:
                    self.session._session['status'][flow['name']] = getattr(self, 'wf_' + flow['name'])()
                except Exception as e:
                    self.session._session['status'][flow['name']] = False
                    logging.exception('Workflow:' + flow['name'] + ':Exception:' + str(e))
                    logging.debug(traceback.format_exc())
                finally:
                    self.wf_progress(flow['name'], self.session._session['status'][flow['name']])

                if span:
                    span.add_binary_annotation('status', str(self.session._session['status'][flow['name']]))
                    span.trace()

                if flow['name'] != Workflow.FLOW_OVER and not self.session.get_status(flow['name']):
                    logging.error('Error during task ' + flow['name'])
                    if flow['name'] != Workflow.FLOW_INIT:
                        self.wf_over()
                    return False
                # Main task is over, execute sub tasks of main
                if not self.skip_all:
                    for step in flow['steps']:
                        span = None
                        try:
                            # Check for cancel request
                            if self.redis_client and self.redis_client.get(self.redis_prefix + ':' + self.bank.name + ':action:cancel'):
                                logging.warn('Cancel requested, stopping update')
                                self.redis_client.delete(self.redis_prefix + ':' + self.bank.name + ':action:cancel')
                                self.wf_over()
                                return False

                            if self.options.get_option('traceId'):
                                trace_id = self.options.get_option('traceId')
                                span_id = self.options.get_option('spanId')
                                span = Zipkin('biomaj-workflow', flow['name'] + ":wf_" + step, trace_id=trace_id, parent_id=span_id)
                                self.span = span
                                self.bank.config.set('zipkin_trace_id', span.get_trace_id())
                                self.bank.config.set('zipkin_span_id', span.get_span_id())
                            res = getattr(self, 'wf_' + step)()

                            if span:
                                span.add_binary_annotation('status', str(res))
                                span.trace()

                            if not res:
                                logging.error('Error during ' + flow['name'] + ' subtask: wf_' + step)
                                logging.error('Revert main task status ' + flow['name'] + ' to error status')
                                self.session._session['status'][flow['name']] = False
                                self.wf_over()
                                return False
                        except Exception as e:
                            logging.error('Workflow:' + flow['name'] + ' subtask: wf_' + step + ':Exception:' + str(e))
                            self.session._session['status'][flow['name']] = False
                            logging.debug(traceback.format_exc())
                            self.wf_over()
                            return False
            dt = datetime.datetime.now()
            end_timestamp = time.mktime(dt.timetuple())
            self.session._session['stats']['workflow'][flow['name']] = end_timestamp - start_timestamp
            if self.options.get_option(Options.STOP_AFTER) == flow['name']:
                self.wf_over()
                break
        self.wf_progress_end()
        return True

    def wf_progress_init(self):
        """
        Set up new progress status
        """
        status = {}
        status['log_file'] = {'status': self.session.config.log_file, 'progress': 0}
        status['session'] = self.session._session['id']
        for flow in self.session.flow:
            if flow['name'] == 'download':
                status[flow['name']] = {'status': None, 'progress': 0, 'total': 0}
            elif flow['name'].endswith('process'):
                status[flow['name']] = {'status': None, 'progress': {}}
            elif flow['name'] == 'release':
                status[flow['name']] = {'status': None, 'progress': ''}
            else:
                status[flow['name']] = {'status': None, 'progress': 0}
        MongoConnector.banks.update({'name': self.name}, {'$set': {'status': status}})

    def wf_progress_end(self):
        """
        Reset progress status when workflow is over
        """
        return True

    def wf_progress(self, task, status):
        """
        Update bank status
        """
        subtask = 'status.' + task + '.status'
        MongoConnector.banks.update({'name': self.name}, {'$set': {subtask: status}})

    def wf_init(self):
        """
        Initialize workflow
        """
        logging.info('Workflow:wf_init')
        data_dir = self.session.config.get('data.dir')
        lock_dir = self.session.config.get('lock.dir', default=data_dir)
        if not os.path.exists(lock_dir):
            os.mkdir(lock_dir)
        lock_file = os.path.join(lock_dir, self.name + '.lock')
        maintenance_lock_file = os.path.join(lock_dir, 'biomaj.lock')
        if os.path.exists(maintenance_lock_file):
            logging.error('Biomaj is in maintenance')
            return False
        if os.path.exists(lock_file):
            logging.error('Bank ' + self.name + ' is locked, a process may be in progress, else remove the lock file ' + lock_file)
            return False
        f = open(lock_file, 'w')
        f.write('1')
        f.close()
        self.wf_progress_init()
        return True

    def wf_over(self):
        """
        Workflow is over
        """
        logging.info('Workflow:wf_over')
        data_dir = self.session.config.get('data.dir')
        lock_dir = self.session.config.get('lock.dir', default=data_dir)
        lock_file = os.path.join(lock_dir, self.name + '.lock')
        if os.path.exists(lock_file):
            os.remove(lock_file)
        return True


class RemoveWorkflow(Workflow):
    """
    Workflow to remove a bank instance
    """

    FLOW = [
        {'name': 'init', 'steps': []},
        {'name': 'removeprocess', 'steps': []},
        {'name': 'remove_release', 'steps': []},
        {'name': 'over', 'steps': []}
    ]

    def __init__(self, bank, session):
        """
        Instantiate a new workflow

        :param bank: bank on which to apply the workflow
        :type bank: Bank
        :param session: session to remove
        :type session: :class:`biomaj.session.Session`
        """
        Workflow.__init__(self, bank, session)
        logging.debug('New workflow')
        self.session._session['remove'] = True

    def wf_remove_release(self):
        logging.info('Workflow:wf_remove_release')
        if not self.session.get('update_session_id'):
            logging.error('Bug: update_session_id not set in session')
            return False

        if os.path.exists(self.session.get_full_release_directory()):
            logging.info('Workflow:wf_remove:delete:' + self.session.get_full_release_directory())
            try:
                shutil.rmtree(self.session.get_full_release_directory())
            except Exception:
                logging.exception('Failed to delete bank release directory: ' + self.session.get_full_release_directory())
                logging.error('Bank will be deleted but some files/dirs may still be present on system, you can safely manually delete them')
        return self.bank.remove_session(self.session.get('update_session_id'))

    def wf_removeprocess(self):
        logging.info('Workflow:wf_removepreprocess')
        metas = self.session._session['process']['removeprocess']
        pfactory = RemoveProcessFactory(self.bank, metas, redis_client=self.redis_client, redis_prefix=self.redis_prefix)
        res = pfactory.run()
        self.session._session['process']['removeprocess'] = pfactory.meta_status
        return res


class UpdateWorkflow(Workflow):
    """
    Workflow for a bank update
    """

    FLOW = [
        {'name': 'init', 'steps': []},
        {'name': 'check', 'steps': []},
        {'name': 'depends', 'steps': []},
        {'name': 'preprocess', 'steps': []},
        {'name': 'release', 'steps': []},
        {'name': 'download', 'steps': ['checksum', 'uncompress', 'copy', 'copydepends']},
        {'name': 'postprocess', 'steps': ['metadata', 'stats']},
        {'name': 'publish', 'steps': ['old_biomaj_api', 'clean_offline', 'delete_old', 'clean_old_sessions']},
        {'name': 'over', 'steps': []}
    ]

    def __init__(self, bank):
        """
        Instantiate a new workflow

        :param bank: bank on which to apply the workflow
        :type bank: Bank
        """
        Workflow.__init__(self, bank)
        logging.debug('New workflow')
        self.session._session['update'] = True

    def _get_plugin(self, name, plugin_args):
        options = {}
        plugins_dir = self.bank.config.get('plugins_dir')
        if not plugins_dir:
            return None
        if plugin_args:
            for plugin_arg in plugin_args.split(','):
                arg = plugin_arg.split('=', 1)
                options[arg[0].strip()] = arg[1].strip()
        requested_plugin = None
        simplePluginManager = PluginManager()
        simplePluginManager.setPluginPlaces([plugins_dir])
        simplePluginManager.collectPlugins()
        logging.error('Load plugins from %s' % (plugins_dir))
        for pluginInfo in simplePluginManager.getAllPlugins():
            if pluginInfo.plugin_object.name() == name:
                requested_plugin = pluginInfo.plugin_object
        if requested_plugin is None:
            return None
        requested_plugin.configure(options)
        return requested_plugin

    def wf_init(self):
        err = super(UpdateWorkflow, self).wf_init()
        if not err:
            return False
        offline_dir = self.session.get_offline_directory()
        if not os.path.exists(offline_dir):
            logging.debug('Create offline directory: %s' % (str(offline_dir)))
            os.makedirs(offline_dir)
        if self.options.get_option(Options.FROMSCRATCH):
            return self.wf_clean_offline()

        return True

    def _md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _sha256(self, fname):
        hash_sha256 = hashlib.sha256()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def wf_checksum(self):
        logging.info('Workflow:wf_checksum')
        '''
        if self.bank.config.get('file.md5.check', 'false') != 'true':
            logging.info('Workflow:wf_checksum:skipping')
            return True
        '''
        offline_dir = self.session.get_offline_directory()
        error = False
        for downloaded_file in self.downloaded_files:
            downloaded_file_name = downloaded_file['name']
            if 'save_as' in downloaded_file:
                downloaded_file_name = downloaded_file['save_as']
            md5_file = os.path.join(offline_dir, downloaded_file_name + '.md5')
            if os.path.exists(md5_file):
                with open(md5_file, 'r') as md5_content:
                    data = md5_content.read().split()
                    md5_cksum = data[0]
                    downloaded_file_md5 = self._md5(os.path.join(offline_dir, downloaded_file_name))
                    logging.debug('Wf_checksum:md5:%s:%s:%s' % (downloaded_file_name, downloaded_file_md5, md5_cksum))
                    if downloaded_file_md5 != md5_cksum:
                        logging.error('Invalid md5 checksum for file %s' % (downloaded_file_name))
                        error = True
            sha256_file = os.path.join(offline_dir, downloaded_file_name + '.sha256')
            if os.path.exists(sha256_file):
                with open(sha256_file, 'r') as sha256_content:
                    data = sha256_content.read().split()
                    sha256_cksum = data[0]
                    downloaded_file_sha256 = self._sha256(os.path.join(offline_dir, downloaded_file_name))
                    logging.debug('Wf_checksum:sha256:%s:%s:%s' % (downloaded_file_name, downloaded_file_sha256, sha256_cksum))
                    if downloaded_file_sha256 != sha256_cksum:
                        logging.error('Invalid sha256 checksum for file %s' % (downloaded_file_name))
                        error = True
        if error:
            return False
        return True

    def wf_check(self):
        """
        Basic checks
        """
        logging.info('Workflow:wf_check')
        return True

    def wf_depends(self):
        """
        Checks bank dependencies with other banks. If bank has dependencies, execute update on other banks first
        """
        logging.info('Workflow:wf_depends')
        # Always rescan depends, there might be a new release
        self.session.set('depends', {})
        res = self.bank.update_dependencies()
        logging.info('Workflow:wf_depends:' + str(res))
        if res and len(self.bank.depends) > 0:
            depend_updated = False
            for bdep in self.bank.depends:
                logging.info('Workflow:wf_depends:' + bdep.name + ':' + str(bdep.session.get('update')))
                if bdep.session.get('update'):
                    depend_updated = True
                    break
            if not depend_updated:
                logging.info('Workflow:wf_depends:no bank updated')
        return res

    def wf_copydepends(self):
        """
        Copy files from dependent banks if needed
        """
        logging.info('Workflow:wf_copydepends')
        deps = self.bank.get_dependencies()
        cf = self.session.config
        for dep in deps:
            if self.bank.config.get(dep + '.files.move'):
                logging.info('Worflow:wf_depends:Files:Move:' + self.bank.config.get(dep + '.files.move'))
                bdir = None
                for bdep in self.bank.depends:
                    if bdep.name == dep:
                        bdir = bdep.session.get_full_release_directory()
                        break
                if bdir is None:
                    logging.error('Could not find a session update for bank ' + dep)
                    return False
                # b = self.bank.get_bank(dep, no_log=True)
                locald = LocalDownload(
                    bdir,
                    use_hardlinks=cf.get_bool("use_hardlinks", default=False)
                )
                (file_list, dir_list) = locald.list()
                locald.match(self.bank.config.get(dep + '.files.move').split(), file_list, dir_list)
                bankdepdir = self.bank.session.get_full_release_directory() + "/" + dep
                if not os.path.exists(bankdepdir):
                    os.mkdir(bankdepdir)
                downloadedfiles = locald.download(bankdepdir)
                locald.close()
                if not downloadedfiles:
                    logging.info('Workflow:wf_copydepends:no files to copy')
                    return False
        return True

    def wf_preprocess(self):
        """
        Execute pre-processes
        """
        logging.info('Workflow:wf_preprocess')
        metas = self.session._session['process']['preprocess']
        pfactory = PreProcessFactory(self.bank, metas, redis_client=self.redis_client, redis_prefix=self.redis_prefix)
        res = pfactory.run()
        self.session._session['process']['preprocess'] = pfactory.meta_status
        return res

    def _close_download_service(self, dserv):
        '''
        Cleanup of downloader
        '''
        logging.info("Workflow:DownloadService:CleanSession")
        if dserv:
            dserv.clean()
            dserv.close()

    def __update_info(self, info):
        '''
        Update some info in db for current bank
        '''
        if info is not None:
            MongoConnector.banks.update({'name': self.bank.name},
                                        info)

    def __findLastRelease(self, releases):
        '''
        Try to find most release from releases input array
        '''
        release = releases[0]
        releaseElts = re.split(r'\.|-', release)
        logging.debug('found a release %s' % (release))
        for rel in releases:
            if rel == release:
                continue
            logging.debug('compare next release %s' % (rel))
            relElts = re.split(r'\.|-', rel)
            index = 0
            for relElt in relElts:
                logging.debug("compare release major,minor,etc. : %s >? %s" % (relElt, releaseElts[index]))
                try:
                    if int(relElt) > int(releaseElts[index]):
                        release = rel
                        logging.debug("found newer release %s" % (rel))
                        break
                except ValueError:
                    pass
                finally:
                    index += 1
        return release

    def wf_release(self):
        """
        Find current release on remote
        """
        logging.info('Workflow:wf_release')
        release = None
        cf = self.session.config
        if cf.get('ref.release') and self.bank.depends:
            # Bank is a computed bank and we ask to set release to the same
            # than an other dependant bank
            depbank = self.bank.get_bank(cf.get('ref.release'), no_log=True)
            got_match = False
            got_update = False
            for dep in self.bank.depends:
                if dep.session.get('update'):
                    got_update = True
                if dep.name == depbank.name:
                    self.session.set('release', dep.session.get('release'))
                    self.session.set('remoterelease', dep.session.get('remoterelease'))
                    got_match = True

            if not got_match:
                logging.error('Workflow:wf_release: no release found for bank ' + depbank.name)
                return False

            release = self.session.get('release')
            self.__update_info({'$set': {'status.release.progress': str(release)}})
            '''
            MongoConnector.banks.update({'name': self.bank.name},
                                        {'$set': {'status.release.progress': str(release)}})
            '''

            logging.info('Workflow:wf_release:FromDepends:' + depbank.name + ':' + self.session.get('release'))
            if got_update:
                index = 0
                # Release directory exits, set index to 1
                if os.path.exists(self.session.get_full_release_directory()):
                    index = 1
                for x in range(1, 100):
                    if os.path.exists(self.session.get_full_release_directory() + '__' + str(x)):
                        index = x + 1
                if index > 0:
                    self.session.set('release', release + '__' + str(index))
                    release = release + '__' + str(index)

        self.session.previous_release = self.session.get('previous_release')

        logging.info('Workflow:wf_release:previous_session:' + str(self.session.previous_release))

        if self.session.config.get('release.plugin'):
            # Release already set from a previous run or an other bank
            logging.info('Workflow:wf_release:plugin:' + str(self.session.config.get('release.plugin')))
            plugin = self._get_plugin(self.session.config.get('release.plugin'), self.session.config.get('release.plugin_args'))
            if plugin is None:
                logging.error("Could not load plugin")
                return False
            try:
                plugin_release = plugin.release()
                logging.info('Workflow:wf_release:plugin:%s:%s' % (self.session.config.get('release.plugin'), plugin_release))
                self.session.set('release', plugin_release)
                self.session.set('remoterelease', plugin_release)
                if self.session.previous_release == self.session.get('release') and not self.session.config.get_bool('release.control', default=False):
                    logging.info('Workflow:wf_release:same_as_previous_session')
                    return self.no_need_to_update()
                else:
                    return True
            except Exception as e:
                logging.exception("Plugin failed to get a release %s" % (str(e)))
                return False

        if self.session.get('release'):
            # Release already set from a previous run or an other bank
            logging.info('Workflow:wf_release:session:' + str(self.session.get('release')))
            if self.session.previous_release == self.session.get('release') and not self.session.config.get_bool('release.control', default=False):
                logging.info('Workflow:wf_release:same_as_previous_session')
                return self.no_need_to_update()
            else:
                return True
        if self.session.config.get('release.file') == '' or self.session.config.get('release.file') is None:
            logging.debug('Workflow:wf_release:norelease')
            self.session.set('release', None)
            return True
        else:
            # """""""""""""""""""""""
            dserv = None
            if self.bank.config.get('micro.biomaj.service.download', default=None) == '1':
                dserv = DownloadClient(
                    self.bank.config.get('micro.biomaj.rabbit_mq'),
                    int(self.bank.config.get('micro.biomaj.rabbit_mq_port', default='5672')),
                    self.bank.config.get('micro.biomaj.rabbit_mq_virtualhost', default='/'),
                    self.bank.config.get('micro.biomaj.rabbit_mq_user', default=None),
                    self.bank.config.get('micro.biomaj.rabbit_mq_password', default=None)
                )
            else:
                dserv = DownloadClient()

            proxy = self.bank.config.get('micro.biomaj.proxy.download')
            if not proxy:
                proxy = self.bank.config.get('micro.biomaj.proxy')

            session = dserv.create_session(self.name, proxy)
            logging.info("Workflow:wf_release:DownloadSession:" + str(session))

            http_parse = HTTPParse(
                cf.get('http.parse.dir.line'),
                cf.get('http.parse.file.line'),
                int(cf.get('http.group.dir.name')),
                int(cf.get('http.group.dir.date')),
                int(cf.get('http.group.file.name')),
                int(cf.get('http.group.file.date')),
                cf.get('http.group.file.date_format', default=None),
                int(cf.get('http.group.file.size'))
            )

            proxy = cf.get('proxy')
            if cf.get('release.proxy') is not None:
                proxy = cf.get('release.proxy')

            proxy_auth = cf.get('proxy_auth')
            if cf.get('release.proxy_auth') is not None:
                proxy = cf.get('release.proxy_auth')

            protocol = cf.get('protocol')
            if cf.get('release.protocol') is not None:
                protocol = cf.get('release.protocol')

            server = cf.get('server')
            if cf.get('release.server') is not None:
                server = cf.get('release.server')

            remote_dir = cf.get('remote.dir')
            if cf.get('release.remote.dir') is not None:
                remote_dir = cf.get('release.remote.dir')

            params = None
            keys = cf.get('url.params')
            credentials = cf.get('server.credentials')
            if cf.get('release.credentials') is not None:
                credentials = cf.get('release.credentials')

            save_as = None
            method = 'GET'
            if protocol in ['directftp', 'directftps', 'directhttp', 'directhttps']:
                keys = cf.get('url.params')
                if keys is not None:
                    params = {}
                    keys = keys.split(',')
                    for key in keys:
                        param = cf.get(key.strip() + '.value')
                        params[key.strip()] = param.strip()

                save_as = cf.get('release.file')
                remotes = [remote_dir]
                remote_dir = '/'
                method = cf.get('url.method')
                if cf.get('release.url.method') is not None:
                    method = cf.get('release.url.method')
            # add params for irods to get port, password, user, zone
            if protocol == 'irods':
                keys = None
                keys = str(str(cf.get('irods.user')) + ',' + str(cf.get('irods.password')) + ',' + str(cf.get('irods.port')) + ',' + str(cf.get('irods.protocol')))
                if keys is not None:
                    params = {}
                    keys = str(keys).split(',')
                    params['user'] = str(cf.get('irods.user')).strip()
                    params['password'] = str(cf.get('irods.password')).strip()
                    params['port'] = str(cf.get('irods.port')).strip()
                    params['protocol'] = str(cf.get('irods.protocol')).strip()
                    params['zone'] = str(cf.get('irods.zone')).strip()

            # Protocol options: as for params, a field contains the name
            # of the options (options.names) and the values are in another
            # field named options.<option_name>.
            protocol_options = {}
            option_names = cf.get('options.names')
            if option_names is not None:
                option_names = option_names.split(',')
                for option_name in option_names:
                    option_name = option_name.strip()
                    param = cf.get('options.' + option_name)
                    protocol_options[option_name] = param.strip()
                logging.debug("Protocol options: " + str(protocol_options))

            release_downloader = dserv.get_handler(
                protocol,
                server,
                remote_dir,
                credentials=credentials,
                http_parse=http_parse,
                http_method=method,
                param=params,
                proxy=proxy,
                proxy_auth=proxy_auth,
                save_as=save_as,
                timeout_download=cf.get('timeout.download'),
                offline_dir=self.session.get_offline_directory(),
                protocol_options=protocol_options
            )

            if protocol in ['directftp', 'directftps', 'directhttp', 'directhttps']:
                release_downloader.set_files_to_download(remotes)
            # """"""""""""""""""""""""

            if release_downloader is None:
                logging.error('Protocol ' + protocol + ' not supported')
                self._close_download_service(dserv)
                return False

            try:
                (file_list, dir_list) = release_downloader.list()
            except Exception as e:
                self._close_download_service(dserv)
                logging.exception('Workflow:wf_release:Exception:' + str(e))
                return False

            release_downloader.match([cf.get('release.file')], file_list, dir_list)
            if len(release_downloader.files_to_download) == 0:
                logging.error('release.file defined but does not match any file')
                self._close_download_service(dserv)
                return False
            if len(release_downloader.files_to_download) > 1:
                logging.error('release.file defined but matches multiple files')
                self._close_download_service(dserv)
                return False
            if cf.get('release.regexp') is None or not cf.get('release.regexp'):
                # Try to get from regexp in file name
                rel = re.search(cf.get('release.file'), release_downloader.files_to_download[0]['name'])
                if rel is None:
                    logging.error('release.file defined but does not match any file')
                    self._close_download_service(dserv)
                    return False
                release = rel.group(1)
            else:
                # Download and extract
                tmp_dir = tempfile.mkdtemp('biomaj')
                rel_files = release_downloader.download(tmp_dir)
                rel_file = None
                rel_file_name = rel_files[0]['name']
                if 'save_as' in rel_files[0] and rel_files[0]['save_as']:
                    rel_file_name = rel_files[0]['save_as']
                if (sys.version_info > (3, 0)):
                    rel_file = open(tmp_dir + '/' + rel_file_name, encoding='utf-8', errors='ignore')
                else:
                    rel_file = open(tmp_dir + '/' + rel_file_name)
                rel_content = rel_file.read()
                rel_file.close()
                shutil.rmtree(tmp_dir)
                rel = re.search(cf.get('release.regexp'), rel_content)
                if rel is None:
                    logging.error('release.regexp defined but does not match any file content')
                    self._close_download_service(dserv)
                    return False
                rels = re.findall(cf.get('release.regexp'), rel_content)
                if len(rels) == 1:
                    release = rels[0]
                else:
                    release = self.__findLastRelease(rels)
                '''
                # If regexp contains matching group, else take whole match
                if len(rel.groups()) > 0:
                    release = rel.group(1)
                else:
                    release = rel.group(0)
                '''

            release_downloader.close()
            self._close_download_service(dserv)

            if release_downloader.error:
                logging.error('An error occured during download')
                return False

        self.session.set('release', release)
        self.session.set('remoterelease', release)

        self.__update_info({'$set': {'status.release.progress': str(release)}})
        '''
        MongoConnector.banks.update(
            {'name': self.bank.name},
            {'$set': {'status.release.progress': str(release)}}
        )
        '''

        # We restart from scratch, a directory with this release already exists
        # Check directory existence if from scratch to change local release
        if self.options.get_option(Options.FROMSCRATCH):
            index = 0
            # Release directory exits, set index to 1
            if os.path.exists(self.session.get_full_release_directory()):
                index = 1
            for x in range(1, 100):
                if os.path.exists(self.session.get_full_release_directory() + '__' + str(x)):
                    index = x + 1
            if index > 0:
                self.session.set('release', release + '__' + str(index))
                release = release + '__' + str(index)

        self.download_go_ahead = False
        if self.options.get_option(Options.FROM_TASK) == 'download':
            # We want to download again in same release, that's fine, we do not care it is the same release
            self.download_go_ahead = True

        if not self.download_go_ahead and self.session.previous_release == self.session.get('remoterelease'):
            if not self.session.config.get_bool('release.control', default=False):
                logging.info('Workflow:wf_release:same_as_previous_session')
                return self.no_need_to_update()

        logging.info('Session:RemoteRelease:' + self.session.get('remoterelease'))
        logging.info('Session:Release:' + self.session.get('release'))
        return True

    def no_need_to_update(self):
        """
        Set status to over and update = False because there is not a need to update bank
        """
        self.skip_all = True
        self.session._session['status'][Workflow.FLOW_OVER] = True
        self.wf_progress(Workflow.FLOW_OVER, True)
        self.session._session['update'] = False
        self.session.set('download_files', [])
        self.session.set('files', [])
        last_session = self.get_last_prod_session_for_release(self.session.get('remoterelease'))
        self.session.set('release', last_session['release'])
        self.wf_over()
        return True

    def get_last_prod_session_for_release(self, release):
        """
        find last session matching a release in production
        """
        last_session = None
        for prod in self.bank.bank['production']:
            if prod['remoterelease'] == release:
                # Search session related to this production release
                for s in self.bank.bank['sessions']:
                    if s['id'] == prod['session']:
                        last_session = s
                        break
        return last_session

    def _load_local_files_from_session(self, session_id):
        """
        Load lccal files for sessions from cache directory
        """
        cache_dir = self.bank.config.get('cache.dir')
        f_local_files = None
        file_path = os.path.join(cache_dir, 'local_files_' + str(session_id))
        if not os.path.exists(file_path):
            return f_local_files

        with open(file_path) as data_file:
            f_local_files = json.load(data_file)

        return f_local_files

    def _load_download_files_from_session(self, session_id):
        """
        Load download files for sessions from cache directory
        """
        cache_dir = self.bank.config.get('cache.dir')
        f_downloaded_files = None
        file_path = os.path.join(cache_dir, 'files_' + str(session_id))
        if not os.path.exists(file_path):
            return f_downloaded_files

        with open(file_path) as data_file:
            f_downloaded_files = json.load(data_file)

        return f_downloaded_files

    def is_previous_release_content_identical(self):
        """
        Checks if releases (previous_release and remoterelease) are identical in release id and content.
        Expects release.control parameter to be set to true or 1, else skip control.
        """
        if not self.session.config.get_bool('release.control', default=False):
            return True
        # Different releases, so different
        if self.session.get('remoterelease') != self.session.previous_release:
            logging.info('Workflow:wf_download:DifferentRelease')
            return False
        # Same release number, check further
        previous_release_session = self.get_last_prod_session_for_release(self.session.previous_release)

        if previous_release_session is None:
            return False

        previous_downloaded_files = self._load_download_files_from_session(previous_release_session.get('id'))
        previous_release_session['download_files'] = previous_downloaded_files

        if previous_downloaded_files is None:
            # No info on previous download, consider that base release is enough
            logging.warn('Workflow:wf_download:SameRelease:download_files not available, cannot compare to previous release')
            return True

        nb_elts = len(previous_downloaded_files)

        if self.session.get('download_files') is not None and nb_elts != len(self.session.get('download_files')):
            # Number of files to download vs previously downloaded files differ
            logging.info('Workflow:wf_download:SameRelease:Number of files differ')
            return False
        # Same number of files, check hash of files
        list1 = sorted(previous_downloaded_files, key=lambda k: k['hash'])
        list2 = sorted(self.session.get('download_files'), key=lambda k: k['hash'])
        for index in range(0, nb_elts):
            if list1[index]['hash'] != list2[index]['hash']:
                return False
        return True

    def check_and_incr_release(self):
        """
        Checks if local release already exists on disk. If it exists, create a new
         local release, appending __X to the release.

        :returns: str local release
        """
        index = 0
        release = self.session.get('release')
        # Release directory exits, set index to 1
        if os.path.exists(self.session.get_full_release_directory()):
            index = 1
        for x in range(1, 100):
            if os.path.exists(self.session.get_full_release_directory() + '__' + str(x)):
                index = x + 1

        # If we found a directory for this release:   XX or XX__Y
        if index > 0:
            self.session.set('release', release + '__' + str(index))
            release = release + '__' + str(index)
            logging.info('Workflow:wf_download:release:incr_release:' + release)
        return release

    def _create_dir_structure(self, downloader, offline_dir):
        """
        Create expected directory structure in offline directory before download
        """
        logging.debug('Workflow:wf_download:create_dir_structure:start')
        for rfile in downloader.files_to_download:
            save_as = None
            if 'save_as' not in rfile or rfile['save_as'] is None:
                save_as = rfile['name']
            else:
                save_as = rfile['save_as']

            file_dir = offline_dir + '/' + os.path.dirname(save_as)

            try:
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
            except Exception as e:
                logging.error(e)
        logging.debug('Workflow:wf_download:create_dir_structure:done')

    def _get_list_from_file(self, remote_list):
        """
        Load files to download from a file
        """
        if not os.path.exists(remote_list):
            logging.info("remote.list " + remote_list + " does not exists, we suppose there is no new release available")
            return None

        data = []
        with open(remote_list) as data_file:
            data = json.load(data_file)

        for rfile in data:
            if 'year' not in rfile or 'month' not in rfile or 'day' not in rfile:
                today = datetime.date.today()
                rfile['month'] = today.month
                rfile['day'] = today.day
                rfile['year'] = today.year
            if 'permissions' not in rfile:
                rfile['permissions'] = ''
            if 'group' not in rfile:
                rfile['group'] = ''
            if 'size' not in rfile:
                rfile['size'] = 0
            if 'hash' not in rfile:
                rfile['hash'] = None
            if 'root' not in rfile and self.session.config.get('remote.dir'):
                rfile['root'] = self.session.config.get('remote.dir')
        return data

    def wf_download(self):
        """
        Download remote files or use an available local copy from last production directory if possible.
        """
        logging.info('Workflow:wf_download')
        # flow = self.get_flow(Workflow.FLOW_DOWNLOAD)
        downloader = None
        cf = self.session.config
        self.session.previous_release = self.session.get('previous_release')

        if self.session.get('release') is not None:
            self.session.config.set('localrelease', self.session.get('release'))
            self.session.config.set('remoterelease', self.session.get('remoterelease'))
            if self.session.config.get_bool('releaseonly', default=False):
                return True

        if cf.get('protocol') == 'none':
            if self.session.get('release') is None:
                logging.error('Workflow:wf_download:no download file but no release found')
                return False
            else:
                logging.info('Workflow:wf_download:no download file expected')
                self.downloaded_files = []
                if not os.path.exists(self.session.get_full_release_directory()):
                    os.makedirs(self.session.get_full_release_directory())
                return True

        downloaders = []

        pool_size = self.session.config.get('files.num.threads', default=None)

        dserv = None
        if self.bank.config.get('micro.biomaj.service.download', default=None) == '1':
            dserv = DownloadClient(
                self.bank.config.get('micro.biomaj.rabbit_mq'),
                int(self.bank.config.get('micro.biomaj.rabbit_mq_port', default='5672')),
                self.bank.config.get('micro.biomaj.rabbit_mq_virtualhost', default='/'),
                self.bank.config.get('micro.biomaj.rabbit_mq_user', default=None),
                self.bank.config.get('micro.biomaj.rabbit_mq_password', default=None),
            )
        else:
            dserv = DownloadClient()

        if pool_size:
            dserv.set_queue_size(int(pool_size))

        proxy = self.bank.config.get('micro.biomaj.proxy.download')
        if not proxy:
            proxy = self.bank.config.get('micro.biomaj.proxy')

        session = dserv.create_session(self.name, proxy)
        logging.info("Workflow:wf_download:DownloadSession:" + str(session))

        use_remote_list = False
        use_plugin = False

        http_parse = HTTPParse(
            cf.get('http.parse.dir.line'),
            cf.get('http.parse.file.line'),
            int(cf.get('http.group.dir.name')),
            int(cf.get('http.group.dir.date')),
            int(cf.get('http.group.file.name')),
            int(cf.get('http.group.file.date')),
            cf.get('http.group.file.date_format', default=None),
            int(cf.get('http.group.file.size'))
        )
        proxy = cf.get('proxy')
        proxy_auth = cf.get('proxy_auth')

        if cf.get('protocol') == 'multi':
            """
            Search for:
            protocol = multi
            remote.file.0.protocol = directftp
            remote.file.0.server = ftp.ncbi.org
            remote.file.0.path = /musmusculus/chr1/chr1.fa

            => http://ftp2.fr.debian.org/debian/README.html?key1=value&key2=value2
            remote.file.1.protocol = directhttp
            remote.file.1.server = ftp2.fr.debian.org
            remote.file.1.path = debian/README.html
            remote.file.1.method =  GET
            remote.file.1.params.keys = key1,key2
            remote.file.1.params.key1 = value1
            remote.file.1.params.key2 = value2

            => http://ftp2.fr.debian.org/debian/README.html
                #POST PARAMS:
                  key1=value
                  key2=value2
            remote.file.1.protocol = directhttp
            remote.file.1.server = ftp2.fr.debian.org
            remote.file.1.path = debian/README.html
            remote.file.1.method =  POST
            remote.file.1.params.keys = key1,key2
            remote.file.1.params.key1 = value1
            remote.file.1.params.key2 = value2

            ......
            """
            # Creates multiple downloaders
            i = 0
            rfile = cf.get('remote.file.' + str(i) + '.path')
            server = None
            while rfile is not None:
                protocol = cf.get('protocol')
                if cf.get('remote.file.' + str(i) + '.protocol') is not None:
                    protocol = cf.get('remote.file.' + str(i) + '.protocol')

                server = cf.get('server')
                if cf.get('remote.file.' + str(i) + '.server') is not None:
                    server = cf.get('remote.file.' + str(i) + '.server')

                params = None
                keys = cf.get('remote.file.' + str(i) + '.params.keys')
                if keys is not None:
                    params = {}
                    keys = keys.split(',')
                    for key in keys:
                        param = cf.get('remote.file.' + str(i) + '.params.' + key.strip())
                        params[key.strip()] = param.strip()

                method = cf.get('remote.file.' + str(i) + '.method')
                if method is None:
                    if cf.get('url.method') is not None:
                        method = cf.get('url.method')
                    else:
                        method = 'GET'

                credentials = cf.get('remote.file.' + str(i) + '.credentials')
                if not method:
                    credentials = cf.get('server.credentials')

                remotes = [cf.get('remote.file.' + str(i) + '.path')]

                save_as = cf.get('remote.file.' + str(i) + '.path')
                if cf.get('remote.file.' + str(i) + '.name'):
                    save_as = cf.get('remote.file.' + str(i) + '.name')

                # Protocol options: as for params, a field contains the name
                # of the options (options.names) and the values are in another
                # field named options.<option_name>.
                protocol_options = {}
                option_names = cf.get('remote.file.' + str(i) + '.options.names')
                if option_names is not None:
                    option_names = option_names.split(',')
                    for option_name in option_names:
                        option_name = option_name.strip()
                        param = cf.get('remote.file.' + str(i) + '.options.' + option_name)
                        protocol_options[option_name] = param.strip()
                    logging.debug("Protocol options: " + str(protocol_options))

                subdownloader = dserv.get_handler(
                    protocol,
                    server,
                    '',
                    credentials=credentials,
                    http_parse=http_parse,
                    http_method=method,
                    param=params,
                    proxy=proxy,
                    proxy_auth=proxy_auth,
                    save_as=save_as,
                    timeout_download=cf.get('timeout.download'),
                    offline_dir=self.session.get_offline_directory(),
                    protocol_options=protocol_options
                )
                subdownloader.set_files_to_download(remotes)

                downloaders.append(subdownloader)

                i += 1
                rfile = cf.get('remote.file.' + str(i) + '.path')
        else:
            """
            Simple case, one downloader with regexp
            """
            protocol = cf.get('protocol')
            server = cf.get('server')

            params = None
            method = cf.get('url.method')
            if method is None:
                method = 'GET'

            credentials = cf.get('server.credentials')

            remote_dir = cf.get('remote.dir')

            if protocol in ['directftp', 'directftps', 'directhttp', 'directhttps']:
                keys = cf.get('url.params')
                if keys is not None:
                    params = {}
                    keys = keys.split(',')
                    for key in keys:
                        param = cf.get(key.strip() + '.value')
                        params[key.strip()] = param.strip()

                remotes = [cf.get('remote.dir')[:-1]]
                remote_dir = '/'
            # add params for irods to get port, password, user, zone
            if protocol == 'irods':
                keys = None
                keys = str(str(cf.get('irods.user')) + ',' + str(cf.get('irods.password')) + ',' + str(cf.get('irods.port')) + ',' + str(cf.get('irods.protocol')))
                if keys is not None:
                    params = {}
                    keys = str(keys).split(',')
                    params['user'] = str(cf.get('irods.user')).strip()
                    params['password'] = str(cf.get('irods.password')).strip()
                    params['port'] = str(cf.get('irods.port')).strip()
                    params['protocol'] = str(cf.get('irods.protocol')).strip()
                    params['zone'] = str(cf.get('irods.zone')).strip()

            save_as = cf.get('target.name')

            # Protocol options: as for params, a field contains the name
            # of the options (options.names) and the values are in another
            # field named options.<option_name>.
            protocol_options = {}
            option_names = cf.get('options.names')
            if option_names is not None:
                option_names = option_names.split(',')
                for option_name in option_names:
                    option_name = option_name.strip()
                    param = cf.get('options.' + option_name)
                    protocol_options[option_name] = param.strip()
                logging.debug("Protocol options: " + str(protocol_options))

            downloader = dserv.get_handler(
                protocol,
                server,
                remote_dir,
                credentials=credentials,
                http_parse=http_parse,
                http_method=method,
                param=params,
                proxy=proxy,
                proxy_auth=proxy_auth,
                save_as=save_as,
                timeout_download=cf.get('timeout.download'),
                offline_dir=self.session.get_offline_directory(),
                protocol_options=protocol_options
            )

            if protocol in ['directftp', 'directftps', 'directhttp', 'directhttps']:
                downloader.set_files_to_download(remotes)

            remote_list = cf.get('remote.list', default=None)
            if remote_list is not None:
                logging.info("Use list from " + remote_list)
                downloader.files_to_download = self._get_list_from_file(remote_list)
                use_remote_list = True

            remote_plugin = cf.get('remote.plugin', default=None)
            if remote_plugin is not None:
                logging.info("Use list from plugin %s" % (remote_plugin))
                plugin = self._get_plugin(self.session.config.get('remote.plugin'), self.session.config.get('remote.plugin_args'))
                downloader.files_to_download = plugin.list(self.session.get('release'))
                use_plugin = True

            downloaders.append(downloader)

        self._close_download_service(dserv)

        for downloader in downloaders:
            if downloader is None:
                logging.error('Protocol ' + downloader.protocol + ' not supported')
                return False

        files_to_download = []

        for downloader in downloaders:
            if use_remote_list:
                if not downloader.files_to_download:
                    self.session.set('remoterelease', self.session.previous_release)
                    return self.no_need_to_update()
            elif use_plugin:
                if not downloader.files_to_download:
                    self.session.set('remoterelease', self.session.previous_release)
                    return self.no_need_to_update()
            else:
                (file_list, dir_list) = downloader.list()
                downloader.match(cf.get('remote.files', default='.*').split(), file_list, dir_list)

            # Check if save_as defined, else check if regexp contains some save information with groups
            for f in downloader.files_to_download:
                if 'save_as' not in f or not f['save_as']:
                    f['save_as'] = f['name']
                    for p in cf.get('remote.files', default='.*').split():
                        if p == '.*' or p == '**/*':
                            continue
                        if p.startswith('^'):
                            p = p.replace('^', '^/')
                        else:
                            p = '/' + p
                        res = re.match(p, f['name'])
                        if res is not None and res.groups() is not None and len(res.groups()) >= 1:
                            f['save_as'] = '/'.join(res.groups())
                            break

            files_to_download += downloader.files_to_download

        self.session.set('download_files', downloader.files_to_download)
        self.session._session['stats']['nb_downloaded_files'] = len(files_to_download)
        logging.info('Workflow:wf_download:nb_files_to_download:%d' % (len(files_to_download)))
        if self.session.get('release') and self.session.config.get_bool('release.control', default=False):
            if self.session.previous_release == self.session.get('remoterelease'):
                if self.is_previous_release_content_identical():
                    logging.info('Workflow:wf_release:same_as_previous_session')
                    return self.no_need_to_update()
                else:
                    release = self.check_and_incr_release()

        if self.session.get('release') is None:
            # Not defined, or could not get it ealier
            # Set release to most recent file to download
            release_dict = Utils.get_more_recent_file(downloader.files_to_download)
            if release_dict is None:
                today = datetime.datetime.now()
                release_dict = {'year': today.year, 'month': today.month, 'day': today.day}

            release = str(release_dict['year']) + '-' + str(release_dict['month']) + '-' + str(release_dict['day'])
            if cf.get('release.format'):
                release_date = datetime.datetime.now()
                release_date = release_date.replace(year=int(release_dict['year']), month=int(release_dict['month']), day=int(release_dict['day']))
                # Fix configparser problem between py2 and py3
                release = release_date.strftime(cf.get('release.format').replace('%%', '%'))
            self.session.set('release', release)
            self.session.set('remoterelease', release)

            logging.info('Workflow:wf_download:release:remoterelease:' + self.session.get('remoterelease'))
            logging.info('Workflow:wf_download:release:release:' + release)

            self.__update_info({'$set': {'status.release.progress': str(release)}})
            '''
            MongoConnector.banks.update(
                {'name': self.bank.name},
                {'$set': {'status.release.progress': str(release)}}
            )
            '''
            self.download_go_ahead = False
            if self.options.get_option(Options.FROM_TASK) == 'download':
                # We want to download again in same release, that's fine, we do not care it is the same release
                self.download_go_ahead = True
            if not self.download_go_ahead and self.session.previous_release == self.session.get('remoterelease') and self.is_previous_release_content_identical():
                logging.info('Workflow:wf_release:same_as_previous_session')
                return self.no_need_to_update()

            # We restart from scratch, check if directory with this release already exists
            if self.options.get_option(Options.FROMSCRATCH) or self.options.get_option('release') is None:
                release = self.check_and_incr_release()

        self.session.config.set('localrelease', self.session.get('release'))
        self.session.config.set('remoterelease', self.session.get('remoterelease'))

        if self.session.config.get_bool('releaseonly', default=False):
            return True

        self.banks = MongoConnector.banks
        self.bank.bank = self.banks.find_one({'name': self.name})

        nb_prod_dir = len(self.bank.bank['production'])
        offline_dir = self.session.get_offline_directory()

        copied_files = []

        # Check if already in offlinedir
        files_in_offline = 0
        nb_expected_files = 0
        for downloader in downloaders:
            keep_files = []
            nb_expected_files += len(downloader.files_to_download)
            if os.path.exists(offline_dir):
                logging.debug('Workflow:wf_download:offline_check_dir:' + offline_dir)
                for file_to_download in downloader.files_to_download:
                    # If file is in offline dir and has same date and size, do not download again
                    offline_file = file_to_download['name']
                    if file_to_download.get('save_as', None):
                        offline_file = file_to_download['save_as']
                    logging.debug('Workflow:wf_download:offline_check_file:' + offline_file)
                    if os.path.exists(offline_dir + '/' + offline_file):
                        logging.debug('Workflow:wf_download:offline_check_file_identical:' + offline_file)
                        try:
                            file_stat = os.stat(offline_dir + '/' + offline_file)
                            f_stat = datetime.datetime.fromtimestamp(os.path.getmtime(offline_dir + '/' + offline_file))
                            year = str(f_stat.year)
                            month = str(f_stat.month)
                            day = str(f_stat.day)
                            if str(file_stat.st_size) != str(file_to_download['size']) or \
                               str(year) != str(file_to_download['year']) or \
                               str(month) != str(file_to_download['month']) or \
                               str(day) != str(file_to_download['day']):
                                logging.debug('Workflow:wf_download:different_from_offline:' + offline_file)
                                keep_files.append(file_to_download)
                            else:
                                logging.debug('Workflow:wf_download:same_as_offline:' + offline_file)
                                files_in_offline += 1
                                copied_files.append(file_to_download)
                        except Exception as e:
                            # Could not get stats on file
                            logging.debug('Workflow:wf_download:offline:failed to stat file: ' + str(e))
                            os.remove(offline_dir + '/' + offline_file)
                            keep_files.append(file_to_download)
                    else:
                        keep_files.append(file_to_download)
                downloader.files_to_download = keep_files
        logging.info("Workflow:wf_download:nb_expected_files:" + str(nb_expected_files))
        logging.info("Workflow:wf_download:nb_files_in_offline_dir:" + str(files_in_offline))
        # If everything was already in offline dir
        everything_present = True
        for downloader in downloaders:
            if len(downloader.files_to_download) > 0:
                everything_present = False
                break
        if everything_present:
            self.downloaded_files = []
            logging.info("Workflow:wf_download:all_files_in_offline:skip download")
            return True

        for downloader in downloaders:
            self._create_dir_structure(downloader, offline_dir)

        self.download_go_ahead = False
        if self.options.get_option(Options.FROM_TASK) == 'download':
            # We want to download again in same release, that's fine, we do not care it is the same release
            self.download_go_ahead = True

        if not self.options.get_option(Options.FROMSCRATCH) and not self.download_go_ahead and nb_prod_dir > 0:
            # Get last production
            last_production = self.bank.bank['production'][nb_prod_dir - 1]
            # Get session corresponding to production directory
            last_production_session = self.banks.find_one({'name': self.name, 'sessions.id': last_production['session']}, {'sessions.$': 1})
            last_production_session_release_directory = self.session.get_full_release_directory(release=last_production['release'])
            last_production_dir = os.path.join(last_production_session_release_directory, 'flat')
            # Checks if some files can be copied instead of downloaded
            last_production_files = None
            if len(last_production_session['sessions']) > 0:
                last_production_files = self._load_local_files_from_session(last_production_session['sessions'][0]['id'])

            if not cf.get_bool('copy.skip', default=False):
                for downloader in downloaders:
                    downloader.download_or_copy(last_production_files, last_production_dir)

            everything_copied = True
            for downloader in downloaders:
                if len(downloader.files_to_download) > 0:
                    everything_copied = False
                    break
            if everything_copied:
                logging.info('Workflow:wf_download:all files copied from %s' % (str(last_production_dir)))
                # return self.no_need_to_update()

            logging.debug('Workflow:wf_download:Copy files from ' + last_production_dir)
            for downloader in downloaders:
                copied_files += downloader.files_to_copy
                Utils.copy_files(
                    downloader.files_to_copy, offline_dir,
                    use_hardlinks=cf.get_bool('use_hardlinks', default=False)
                )

        downloader.close()

        pool_size = self.session.config.get('files.num.threads', default=None)
        dserv = None

        if self.bank.config.get('micro.biomaj.service.download', default=None) == '1':
            dserv = DownloadClient(
                self.bank.config.get('micro.biomaj.rabbit_mq'),
                int(self.bank.config.get('micro.biomaj.rabbit_mq_port', default='5672')),
                self.bank.config.get('micro.biomaj.rabbit_mq_virtualhost', default='/'),
                self.bank.config.get('micro.biomaj.rabbit_mq_user', default=None),
                self.bank.config.get('micro.biomaj.rabbit_mq_password', default=None),
                redis_client=self.redis_client,
                redis_prefix=self.redis_prefix
            )
            if pool_size:
                logging.info('Set rate limiting: %s' % (str(pool_size)))
                dserv.set_rate_limiting(int(pool_size))

        else:
            dserv = DownloadClient()

        if pool_size:
            dserv.set_queue_size(int(pool_size))

        proxy = self.bank.config.get('micro.biomaj.proxy.download')
        if not proxy:
            proxy = self.bank.config.get('micro.biomaj.proxy')

        session = dserv.create_session(self.name, proxy)
        logging.info("Workflow:wf_download:DownloadSession:" + str(session))

        for downloader in downloaders:
            for file_to_download in downloader.files_to_download:
                operation = downmessage_pb2.Operation()
                operation.type = 1
                message = downmessage_pb2.DownloadFile()
                message.bank = self.name
                message.session = session
                message.local_dir = offline_dir
                message.protocol_options.update(downloader.protocol_options)
                remote_file = downmessage_pb2.DownloadFile.RemoteFile()
                protocol = downloader.protocol
                remote_file.protocol = downmessage_pb2.DownloadFile.Protocol.Value(protocol.upper())

                if downloader.credentials:
                    remote_file.credentials = downloader.credentials

                remote_file.server = downloader.server
                if cf.get('remote.dir'):
                    remote_file.remote_dir = cf.get('remote.dir')
                else:
                    remote_file.remote_dir = ''

                if http_parse:
                    msg_http_parse = downmessage_pb2.DownloadFile.HttpParse()
                    msg_http_parse.dir_line = http_parse.dir_line
                    msg_http_parse.file_line = http_parse.file_line
                    msg_http_parse.dir_name = http_parse.dir_name
                    msg_http_parse.dir_date = http_parse.dir_date
                    msg_http_parse.file_name = http_parse.file_name
                    msg_http_parse.file_date = http_parse.file_date
                    msg_http_parse.file_size = http_parse.file_size
                    if http_parse.file_date_format:
                        msg_http_parse.file_date_format = http_parse.file_date_format
                    remote_file.http_parse.MergeFrom(msg_http_parse)

                biomaj_file = remote_file.files.add()
                biomaj_file.name = file_to_download['name']
                if 'root' in file_to_download and file_to_download['root']:
                    biomaj_file.root = file_to_download['root']
                if downloader.param:
                    for key in list(downloader.param.keys()):
                        param = remote_file.param.add()
                        param.name = key
                        param.value = downloader.param[key]
                if 'save_as' in file_to_download and file_to_download['save_as']:
                    biomaj_file.save_as = file_to_download['save_as']
                if 'url' in file_to_download and file_to_download['url']:
                    biomaj_file.url = file_to_download['url']
                if 'permissions' in file_to_download and file_to_download['permissions']:
                    biomaj_file.metadata.permissions = file_to_download['permissions']
                if 'size' in file_to_download and file_to_download['size']:
                    biomaj_file.metadata.size = file_to_download['size']
                if 'year' in file_to_download and file_to_download['year']:
                    biomaj_file.metadata.year = file_to_download['year']
                if 'month' in file_to_download and file_to_download['month']:
                    biomaj_file.metadata.month = file_to_download['month']
                if 'day' in file_to_download and file_to_download['day']:
                    biomaj_file.metadata.day = file_to_download['day']
                if 'hash' in file_to_download and file_to_download['hash']:
                    biomaj_file.metadata.hash = file_to_download['hash']
                if 'md5' in file_to_download and file_to_download['md5']:
                    biomaj_file.metadata.md5 = file_to_download['md5']

                message.http_method = downmessage_pb2.DownloadFile.HTTP_METHOD.Value(downloader.method.upper())

                timeout_download = cf.get('timeout.download', default=None)
                if timeout_download:
                    try:
                        message.timeout_download = int(timeout_download)
                    except Exception as e:
                        logging.error('Wrong timeout type for timeout.download: ' + str(e))

                if self.span:
                    trace = downmessage_pb2.Operation.Trace()
                    trace.trace_id = self.span.get_trace_id()
                    trace.span_id = self.span.get_span_id()
                    operation.trace.MergeFrom(trace)

                message.remote_file.MergeFrom(remote_file)
                operation.download.MergeFrom(message)
                dserv.download_remote_file(operation)

        logging.info("Workflow:wf_download:Download:Waiting")
        download_error = False
        try:
            download_plugin = cf.get('download.plugin', default=None)
            if download_plugin is not None:
                self.downloaded_files = copied_files
                logging.info("Use download from plugin %s" % (download_plugin))
                plugin = self._get_plugin(self.session.config.get('download.plugin'), self.session.config.get('remote.plugin_args'))
                if not hasattr(plugin, 'download'):
                    logging.error('Workflow:wf_download:Plugin:%s:Error: plugin does not have a download method' % (download_plugin))
                    return False
                res = plugin.download(self.session.get('release'), downloader.files_to_download, offline_dir=offline_dir)
                self._close_download_service(dserv)
                self.downloaded_files += downloader.files_to_download
                return res

            download_error = dserv.wait_for_download()
        except Exception as e:
            self._close_download_service(dserv)
            logging.exception('Workflow:wf_download:Exception:' + str(e))
            return False
        except KeyboardInterrupt:
            logging.warn("Ctrl-c received! Stop downloads...")
            logging.warn("Running downloads will continue and process will stop.")
            self._close_download_service(dserv)
            return False

        self._close_download_service(dserv)

        self.downloaded_files = copied_files
        for downloader in downloaders:
            self.downloaded_files += downloader.files_to_download

        if download_error:
            logging.error('An error occured during download')
            return False

        return True

    def wf_uncompress(self):
        """
        Uncompress files if archives and no.extract = false
        """
        logging.info('Workflow:wf_uncompress')
        if len(self.downloaded_files) == 0:
            logging.info("Workflow:wf_uncompress:NoFileDownload:NoExtract")
            return True
        no_extract = self.session.config.get('no.extract')
        if no_extract is None or no_extract == 'false':
            archives = []
            for file in self.downloaded_files:
                if 'save_as' not in file:
                    file['save_as'] = file['name']
                nb_try = 1
                origFile = self.session.get_offline_directory() + '/' + file['save_as']
                is_archive = False
                if origFile.endswith('.tar.gz'):
                    is_archive = True
                elif origFile.endswith('.tar'):
                    is_archive = True
                elif origFile.endswith('.bz2'):
                    is_archive = True
                elif origFile.endswith('.gz'):
                    is_archive = True
                elif origFile.endswith('.zip'):
                    is_archive = True

                logging.info('Workflow:wf_uncompress:Uncompress:' + origFile)
                if not os.path.exists(origFile):
                    logging.warn('Workflow:wf_uncompress:NotExists:' + origFile)
                    continue

                tmpCompressedFile = origFile
                if is_archive:
                    tmpFileNameElts = file['save_as'].split('/')
                    tmpFileNameElts[len(tmpFileNameElts) - 1] = 'tmp_' + tmpFileNameElts[len(tmpFileNameElts) - 1]
                    tmpCompressedFile = self.session.get_offline_directory() + '/' + '/'.join(tmpFileNameElts)
                    archives.append({'from': origFile, 'to': tmpCompressedFile})
                else:
                    continue

                shutil.copy(origFile, tmpCompressedFile)

                not_ok = True
                while nb_try < 3 and not_ok:
                    status = Utils.uncompress(origFile)
                    if status:
                        not_ok = False
                    else:
                        logging.warn('Workflow:wf_uncompress:Failure:' + file['name'] + ':' + str(nb_try))
                        nb_try += 1
                if not_ok:
                    logging.error('Workflow:wf_uncompress:Failure:' + file['name'])
                    # Revert archive files
                    for archive in archives:
                        if os.path.exists(archive['to']):
                            logging.info("Workflow:wf_uncompress:RevertArchive:" + archive['from'])
                            shutil.move(archive['to'], archive['from'])
                    return False
            for archive in archives:
                if os.path.exists(archive['to']):
                    logging.info("Workflow:wf_uncompress:RemoveAfterExtract:" + archive['to'])
                    os.remove(archive['to'])

        else:
            logging.info("Workflow:wf_uncompress:NoExtract")
        return True

    def wf_copy(self):
        """
        Copy files from offline directory to release directory
        """
        logging.info('Workflow:wf_copy')
        if len(self.downloaded_files) == 0:
            logging.info("Workflow:wf_copy:NoFileDownload:NoCopy")
            return True
        from_dir = os.path.join(self.session.config.get('data.dir'),
                                self.session.config.get('offline.dir.name'))
        regexp = self.session.config.get('local.files', default='**/*').split()
        to_dir = os.path.join(
            self.session.config.get('data.dir'),
            self.session.config.get('dir.version'),
            self.session.get_release_directory(),
            'flat'
        )
        # We use move=True so there is no need to try to use hardlinks here
        local_files = Utils.copy_files_with_regexp(from_dir, to_dir, regexp, True)
        self.session._session['files'] = local_files
        if len(self.session._session['files']) == 0:
            logging.error('Workflow:wf_copy:No file match in offline dir')
            return False
        return True

    def wf_metadata(self):
        """
        Update metadata with info gathered from processes
        """
        logging.info('Workflow:wf_metadata')
        self.bank.session.set('formats', {})
        per_process_meta_data = self.session.get('per_process_metadata')
        for proc in list(per_process_meta_data.keys()):
            for meta_data in list(per_process_meta_data[proc].keys()):
                session_formats = self.bank.session.get('formats')
                if meta_data not in session_formats:
                    session_formats[meta_data] = per_process_meta_data[proc][meta_data]
                else:
                    session_formats[meta_data] += per_process_meta_data[proc][meta_data]
        return True

    def wf_stats(self):
        """
        Get some stats from current release data dir
        """
        logging.info('Workflow:wf_stats')
        do_stats = self.bank.config.get('data.stats')
        if do_stats is None or do_stats == '0':
            self.session.set('fullsize', 0)
            return True
        prod_dir = self.session.get_full_release_directory()
        dir_size = Utils.get_folder_size(prod_dir)
        self.session.set('fullsize', dir_size)
        return True

    def wf_postprocess(self):
        """
        Execute post processes
        """
        # Creates a temporary symlink future_release to keep compatibility if process
        # tries to access dir with this name
        future_link = os.path.join(
            self.bank.config.get('data.dir'),
            self.bank.config.get('dir.version'),
            'future_release'
        )
        # prod_dir = self.session.get_full_release_directory()
        to_dir = os.path.join(
            self.bank.config.get('data.dir'),
            self.bank.config.get('dir.version')
        )

        if os.path.lexists(future_link):
            os.remove(future_link)
        os.chdir(to_dir)
        os.symlink(self.session.get_release_directory(), 'future_release')

        logging.info('Workflow:wf_postprocess')
        blocks = self.session._session['process']['postprocess']
        pfactory = PostProcessFactory(self.bank, blocks, redis_client=self.redis_client, redis_prefix=self.redis_prefix)
        res = pfactory.run()
        self.session._session['process']['postprocess'] = pfactory.blocks

        # In any way, delete symlink
        if os.path.lexists(future_link):
            os.remove(future_link)

        return res

    def wf_publish(self):
        """
        Add *current* symlink to this release
        """
        if self.bank.config.get_bool('auto_publish', default=False):
            logging.info('Workflow:wf_publish')
            self.bank.publish()
            return True

        if not self.options.get_option(Options.PUBLISH):
            logging.info('Workflow:wf_publish:no')
            return True
        logging.info('Workflow:wf_publish')
        self.bank.publish()
        return True

    def wf_old_biomaj_api(self):
        """
        Generates a listing.format file containing the list of files in directories declared in formats
        """
        release_dir = self.session.get_full_release_directory()
        for release_format in self.bank.session.get('formats'):
            format_file = os.path.join(release_dir, 'listingv1.' + release_format.replace('/', '_'))
            section = self.list_section(release_dir, release_format, release_format)
            logging.debug("Worfklow:OldAPI:WriteListing: " + format_file)
            fd = os.open(format_file, os.O_RDWR | os.O_CREAT)
            os.write(fd, json.dumps(section).encode('utf-8'))
            os.close(fd)
        return True

    def list_section(self, base_dir, release_format, base_format):
        """
        Get section files and sub-section from base_dir for directory release_format

        :param base_dir: root directory
        :type base_dir: str
        :param base_dir: sub directory to scan
        :type base_dir: str
        :param base_format: first directroy indicating format
        :type base_format: str
        :return: dict section details
        """
        section = {"name": release_format, "sections": [], "files": []}
        format_dir = os.path.join(base_dir, release_format)
        if not os.path.exists(format_dir):
            logging.info("Worfklow:OldAPI:Format directory " + release_format + " does not exists, skipping")
            return section
        format_dir_list = os.listdir(format_dir)
        for format_dir_file in format_dir_list:
            if os.path.isfile(os.path.join(format_dir, format_dir_file)):
                if base_format.lower() == 'blast':
                    if format_dir_file.endswith('.nal'):
                        fileName, fileExtension = os.path.splitext(format_dir_file)
                        section['files'].append(os.path.join(format_dir, fileName))
                else:
                    section['files'].append(os.path.join(format_dir, format_dir_file))
            else:
                # This is a sub directory
                new_section = self.list_section(format_dir, format_dir_file, base_format)
                section['sections'].append(new_section)
        return section

    def wf_clean_offline(self):
        """
        Clean offline directory
        """
        logging.info('Workflow:wf_clean_offline')
        if os.path.exists(self.session.get_offline_directory()):
            shutil.rmtree(self.session.get_offline_directory())
        return True

    def wf_clean_old_sessions(self):
        """
        Delete old sessions not related to a production directory or last run
        """
        logging.info('Workflow:wf_clean_old_sessions')
        self.bank.clean_old_sessions()
        return True

    def wf_delete_old(self):
        """
        Delete old production dirs
        """
        logging.info('Workflow:wf_delete_old')
        if self.options.get_option(Options.FROM_TASK) is not None:
            # This is a run on an already present release, skip delete
            logging.info('Workflow:wf_delete_old:Skip')
            return True
        if not self.session.config.get('keep.old.version'):
            keep = 1
        else:
            keep = int(self.session.config.get('keep.old.version'))
        # Current production dir is not yet in list
        nb_prod = len(self.bank.bank['production'])
        # save session during delete workflow
        keep_session = self.bank.session
        old_deleted = False
        if nb_prod > keep:
            for prod in self.bank.bank['production']:
                if prod['release'] == keep_session.get('release'):
                    logging.info('Release %s tagged as keep_session, skipping' % (str(prod['release'])))
                    continue
                if 'freeze' in prod and prod['freeze']:
                    logging.info('Release %s tagged as freezed, skipping' % (str(prod['release'])))
                    continue
                if self.bank.bank['current'] == prod['session']:
                    logging.info('Release %s tagged as current, skipping' % (str(prod['release'])))
                    continue
                if nb_prod - keep > 0:
                    nb_prod -= 1
                    session = self.bank.get_new_session(RemoveWorkflow.FLOW)
                    # Delete init and over because we are already in a run
                    i_init = -1
                    i_over = -1
                    for i in range(0, len(session.flow)):
                        if session.flow[i]['name'] == 'init':
                            i_init = i
                    if i_init >= 0:
                        del session.flow[i_init]
                    for i in range(0, len(session.flow)):
                        if session.flow[i]['name'] == 'over':
                            i_over = i
                    if i_over >= 0:
                        del session.flow[i_over]

                    session.set('action', 'remove')
                    session.set('release', prod['release'])
                    session.set('remoterelease', prod['remoterelease'])
                    session.set('update_session_id', prod['session'])
                    logging.info('Workflow:wf_delete_old:Delete:' + prod['release'])
                    res = self.bank.start_remove(session)
                    if not res:
                        logging.error('Workflow:wf_delete_old:ErrorDelete:' + prod['release'])
                    else:
                        old_deleted = True
                else:
                    break
        # Set session back
        self.bank.session = keep_session
        if old_deleted:
            self.bank.session._session['remove'] = True

        return True


class ReleaseCheckWorkflow(UpdateWorkflow):
    """
    Workflow for a bank update
    """

    FLOW = [
        {'name': 'init', 'steps': []},
        {'name': 'check', 'steps': []},
        {'name': 'preprocess', 'steps': []},
        {'name': 'release', 'steps': []},
        {'name': 'download', 'steps': []},
        {'name': 'over', 'steps': []}
    ]

    def __init__(self, bank):
        """
        Instantiate a new workflow

        :param bank: bank on which to apply the workflow
        :type bank: Bank
        """
        UpdateWorkflow.__init__(self, bank)
        logging.debug('New release check workflow')
        self.session.config.set('releaseonly', 'true')

    def wf_init(self):
        """
        Initialize workflow, do not lock bank as it is not modified
        If bank is already locked, stop workflow
        """
        logging.info('Workflow:wf_init')
        data_dir = self.session.config.get('data.dir')
        lock_dir = self.session.config.get('lock.dir', default=data_dir)
        lock_file = os.path.join(lock_dir, self.name + '.lock')
        if os.path.exists(lock_file):
            logging.error('Bank ' + self.name + ' is locked, a process may be in progress, else remove the lock file ' + lock_file)
            return False
        return True

    def wf_over(self):
        """
        Workflow is over
        """
        logging.info('Workflow:wf_over')
        return True

    def __update_info(self, info):
        return

    def wf_progress(self, task, status):
        return


class RepairWorkflow(UpdateWorkflow):
    """
    Workflow to repaire a bank i.e. unlock bank and set all steps to OK (after a manual repair for example)
    """

    def __init__(self, bank):
        """
        Instantiate a new workflow

        :param bank: bank on which to apply the workflow
        :type bank: Bank
        :param session: session to remove
        :type session: :class:`biomaj.session.Session`
        """
        self.wf_unlock(bank)
        UpdateWorkflow.__init__(self, bank)
        self.skip_all = True

    def wf_unlock(self, bank):
        logging.info('Workflow:wf_unlock')
        data_dir = bank.session.config.get('data.dir')
        lock_dir = bank.session.config.get('lock.dir', default=data_dir)
        lock_file = os.path.join(lock_dir, bank.name + '.lock')
        maintenance_lock_file = os.path.join(lock_dir, 'biomaj.lock')
        if os.path.exists(maintenance_lock_file):
            logging.error('Biomaj is in maintenance')
            return False
        if os.path.exists(lock_file):
            os.remove(lock_file)
        return True

    def start(self):
        if self.session.get('release') is None:
            logging.warn('cannot repair bank, no known release')
            return True
        Workflow.start(self)
        self.wf_over()
        return True
