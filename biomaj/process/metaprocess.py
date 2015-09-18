from builtins import str
import threading
import logging
import os

from biomaj.process.process import Process, DrmaaProcess, DockerProcess
from biomaj.mongo_connector import MongoConnector

class MetaProcess(threading.Thread):
    '''
    Meta process in biomaj process workflow. Meta processes are executed in parallel.

    Each meta process defined a list of Process to execute sequentially
    '''

    def __init__(self, bank, metas, meta_status=None, meta_data=None, simulate=False):
        '''
        Creates a meta process thread

        :param bank: Bank
        :type bank: :class:`biomak.bank`
        :param meta: list of meta processes to execute in thread
        :type meta: list of str
        :param meta_status: initial status of the meta processes
        :type meta_status: bool
        :param simulate: does not execute process
        :type simulate: bool
        '''
        if meta_data is None:
            meta_data = {}
        threading.Thread.__init__(self)
        self._lock = None
        self.kill_received = False
        self.workflow = None
        self.simulate = simulate
        self.bank = bank
        self.metas = metas
        self.meta_data = meta_data
        self.meta_status = {}
        for meta in self.metas:
            self.meta_status[meta] = {}

        if meta_status is not None:
            self.meta_status = meta_status

        self._stopevent = threading.Event()

        self.bmaj_env = os.environ.copy()
        #self.bmaj_env = {}
        # Copy all config from bank


        self.bmaj_only_env = {}
        #The root directory where all databases are stored.
        #If your data is not stored under one directory hirearchy
        #you can override this value in the database properties file.
        for conf in dict(self.bank.config.config_bank.items('GENERAL')):
            self.bmaj_env[conf] = self.bank.config.config_bank.get('GENERAL', conf)
            if self.bmaj_env[conf] is None:
                self.bmaj_env[conf] = ''
                self.bmaj_only_env[conf] = self.bmaj_env[conf]

        self.bmaj_env['dbname'] = self.bank.name
        self.bmaj_only_env['dbname'] = self.bmaj_env['dbname']

        self.bmaj_env['datadir'] = self.bank.config.get('data.dir')
        self.bmaj_only_env['datadir'] = self.bmaj_env['datadir']

        self.bmaj_env['data.dir'] = self.bmaj_env['datadir']
        self.bmaj_only_env['data.dir'] = self.bmaj_env['data.dir']

        if self.bank.config.get('mail.admin'):
            self.bmaj_env['mailadmin'] = self.bank.config.get('mail.admin')
            self.bmaj_only_env['mailadmin'] = self.bmaj_env['mailadmin']

        if self.bank.config.get('mail.smtp.host'):
            self.bmaj_env['mailsmtp'] = self.bank.config.get('mail.smtp.host')
            self.bmaj_only_env['mailsmtp'] = self.bmaj_env['mailsmtp']

        self.bmaj_env['processdir'] = self.bank.config.get('process.dir', default='')
        self.bmaj_only_env['processdir'] = self.bmaj_env['processdir']

        if 'PATH' in self.bmaj_env:
            self.bmaj_env['PATH'] += ':' + self.bmaj_env['processdir']
            self.bmaj_only_env['PATH'] = self.bmaj_env['PATH']
        else:
            self.bmaj_env['PATH'] = self.bmaj_env['processdir']+':/usr/local/bin:/usr/sbin:/usr/bin'
            self.bmaj_only_env['PATH'] = self.bmaj_env['PATH']

        self.bmaj_env['PP_DEPENDENCE'] = '#'
        self.bmaj_only_env['PP_DEPENDENCE'] = '#'
        self.bmaj_env['PP_DEPENDENCE_VOLATILE'] = '#'
        self.bmaj_only_env['PP_DEPENDENCE_VOLATILE'] = '#'
        self.bmaj_env['PP_WARNING'] = '#'
        self.bmaj_only_env['PP_WARNING'] = '#'

        self.bmaj_env['PATH_PROCESS_BIOMAJ'] = self.bank.config.get('process.dir')
        self.bmaj_only_env['PATH_PROCESS_BIOMAJ'] = self.bank.config.get('process.dir')

        # Set some session specific env
        if self.bank.session is not None:

            if self.bank.session.get('log_file') is not None:
                log_file = self.bank.session.get('log_file')
                log_dir = os.path.dirname(log_file)
                self.bmaj_env['logdir'] = log_dir
                self.bmaj_only_env['logdir'] = log_dir
                self.bmaj_env['logfile'] = log_file
                self.bmaj_only_env['logfile'] = log_file


            self.bmaj_env['offlinedir'] = self.bank.session.get_offline_directory()
            self.bmaj_only_env['offlinedir'] = self.bmaj_env['offlinedir']

            self.bmaj_env['dirversion'] = self.bank.config.get('dir.version')
            self.bmaj_only_env['dirversion'] = self.bmaj_env['dirversion']

            self.bmaj_env['noextract'] = self.bank.config.get('no.extract')
            if self.bmaj_env['noextract'] is None:
                self.bmaj_env['noextract'] = ''
            self.bmaj_only_env['noextract'] = self.bmaj_env['noextract']

            self.bmaj_env['localrelease'] = self.bank.session.get_release_directory()
            self.bmaj_only_env['localrelease'] = self.bmaj_env['localrelease']
            if self.bank.session.get('release') is not None:
                self.bmaj_env['remoterelease'] = self.bank.session.get('remoterelease')
                self.bmaj_only_env['remoterelease'] = self.bmaj_env['remoterelease']
                self.bmaj_env['removedrelease'] = self.bank.session.get('release')
                self.bmaj_only_env['removedrelease'] = self.bmaj_env['removedrelease']

        for bdep in self.bank.depends:
            self.bmaj_env[bdep.name+'source'] = bdep.session.get_full_release_directory()
            self.bmaj_only_env[bdep.name+'source'] = self.bmaj_env[bdep.name+'source']

        # Fix case where a var = None
        for key in list(self.bmaj_only_env.keys()):
            if self.bmaj_only_env[key] is None:
                self.bmaj_env[key] = ''
                self.bmaj_only_env[key] = ''


    def set_progress(self, name, status=None):
        '''
        Update progress on download

        :param name: name of process
        :type name: str
        :param status: status of process
        :type status: bool or None
        '''
        logging.debug('Process:progress:'+name+"="+str(status))
        if self.workflow is not None:
            MongoConnector.banks.update({'name': self.bank.name},
                {'$set': {'status.'+self.workflow+'.progress.'+name: status}})

    def run(self):
        # Run meta processes
        self.global_status = True
        for meta in self.metas:
            if not self._stopevent.isSet():
                logging.info("PROC:META:RUN:"+meta)
                processes = []
                if self.bank.config.get(meta) is not None:
                    processes = self.bank.config.get(meta).split(',')
                processes_status = {}
                for bprocess in processes:
                    if self.kill_received:
                        raise Exception('Kill request received, exiting')
                    # Process status already ok, do not replay
                    if meta in self.meta_status and bprocess in self.meta_status[meta] and self.meta_status[meta][bprocess]:
                        logging.info("PROC:META:SKIP:PROCESS:"+bprocess)
                        processes_status[bprocess] = True
                        continue
                    logging.info("PROC:META:RUN:PROCESS:"+bprocess)
                    # bprocess.name may not be unique
                    #name = self.bank.config.get(bprocess+'.name')
                    name = bprocess
                    desc = self.bank.config.get(bprocess+'.desc')
                    cluster = self.bank.config.get_bool(bprocess+'.cluster', default=False)
                    docker = self.bank.config.get(bprocess+'.docker')
                    proc_type = self.bank.config.get(bprocess+'.type')
                    exe = self.bank.config.get(bprocess+'.exe')
                    args = self.bank.config.get(bprocess+'.args')
                    expand = self.bank.config.get_bool(bprocess+'.expand', default=True)
                    if cluster:
                        native = self.bank.config.get(bprocess+'.native')
                        bmaj_process = DrmaaProcess(meta+'_'+name, exe, args, desc, proc_type, native,
                                                        expand, self.bmaj_env,
                                                        os.path.dirname(self.bank.config.log_file))
                    elif docker:
                        use_sudo = self.bank.config.get_bool('docker.sudo', default=True)
                        bmaj_process = DockerProcess(meta+'_'+name, exe, args, desc, proc_type, docker,
                                                        expand, self.bmaj_only_env,
                                                        os.path.dirname(self.bank.config.log_file), use_sudo)
                    else:
                        bmaj_process = Process(meta+'_'+name, exe, args, desc, proc_type,
                                                expand, self.bmaj_env, os.path.dirname(self.bank.config.log_file))
                    self.set_progress(bmaj_process.name, None)
                    if self.bank.config.get(bprocess+'.format'):
                        bmaj_process.format = self.bank.config.get(bprocess+'.format')
                    if self.bank.config.get(bprocess+'.types'):
                        bmaj_process.types = self.bank.config.get(bprocess+'.types')
                    if self.bank.config.get(bprocess+'.tags'):
                        bmaj_process.tags = self.bank.config.get(bprocess+'.tags')
                    if self.bank.config.get(bprocess+'.files'):
                        bmaj_process.files = self.bank.config.get(bprocess+'.files')
                    res = bmaj_process.run(self.simulate)
                    processes_status[bprocess] = res
                    self.set_progress(bmaj_process.name, res)
                    if not res:
                        self.global_status = False
                        break
                    if not self.simulate:
                        if self._lock:
                            self._lock.acquire()
                            try:
                                self._get_metata_from_outputfile(bmaj_process)
                            except Exception as e:
                                logging.error(e)
                            finally:
                                self._lock.release() # release lock, no matter what
                        else:
                            self._get_metata_from_outputfile(bmaj_process)
            self.meta_status[meta] = processes_status

    def _get_metata_from_outputfile(self, proc):
        '''
        Extract metadata given by process on stdout. Store metadata in self.metadata

        :param proc: process
        :type proc_name: :class:`biomaj.process.Process`
        '''
        proc_name = proc.name
        output_file = proc.output_file

        self.meta_data[proc_name] = {}
        with open(output_file) as f:
            for line in f:
                if line.startswith('##BIOMAJ#'):
                    line = line.replace('##BIOMAJ#', '')
                    line = line.strip('\n\r')
                    metas = line.split('#')
                    meta_format = metas[0]
                    if meta_format == '':
                        meta_format = proc.format
                    meta_type = metas[1]
                    if meta_type == '':
                        meta_type = proc.types
                    meta_tags = metas[2]
                    if meta_tags == '':
                        meta_tags = proc.tags
                    meta_files = metas[3]
                    if not meta_format in self.meta_data[proc_name]:
                        self.meta_data[proc_name][meta_format] = []
                    tags = meta_tags.split(',')
                    tag_list = {}
                    if meta_tags != '':
                        for tag in tags:
                            t = tag.split(':')
                            tag_list[t[0]] = t[1]
                    self.meta_data[proc_name][meta_format].append({'tags': tag_list,
                                                        'types': meta_type.split(','),
                                                        'files': meta_files.split(',')})
        if proc.files and proc.format:
            tag_list = {}
            if proc.tags != '':
                for tag in proc.tags.split(','):
                    t = tag.split(':')
                    tag_list[t[0]] = t[1]
            self.meta_data[proc_name][proc.format] = []
            self.meta_data[proc_name][proc.format].append({'tags': tag_list,
                                                'types': proc.types.split(','),
                                                'files': proc.files.split(',')})


    def stop(self):
        self._stopevent.set()
