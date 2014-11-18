import threading
import logging
import os

from biomaj.process.process import Process

class MetaProcess(threading.Thread):
    '''
    Meta process in biomaj process workflow. Meta processes are executed in parallel.

    Each meta process defined a list of Process to execute sequentially
    '''

    def __init__(self, bank, metas, meta_status=None, simulate=False):
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
      threading.Thread.__init__(self)
      self.simulate = simulate
      self.bank = bank
      self.metas = metas
      self.meta_data = {}
      self.meta_status = {}
      for meta in self.metas:
        self.meta_status[meta] = {}

      if meta_status is not None:
        self.meta_status = meta_status

      self._stopevent = threading.Event( )

      self.bmaj_env = os.environ.copy();
      #self.bmaj_env = {}
      # Copy all config from bank
      for conf in dict(self.bank.config.config_bank.items('GENERAL')):
        self.bmaj_env[conf] = self.bank.config.config_bank.get('GENERAL', conf)
        if self.bmaj_env[conf] is None:
          self.bmaj_env[conf] = ''

      self.bmaj_env['dbname'] = self.bank.name
      self.bmaj_env['datadir'] = self.bank.config.get('data.dir')
      self.bmaj_env['mailadmin'] = self.bank.config.get('mail.admin')
      self.bmaj_env['mailsmtp'] = self.bank.config.get('mail.smtp.host')
      self.bmaj_env['processdir'] = self.bank.config.get('process.dir',default='')
      if 'PATH' in self.bmaj_env:
        self.bmaj_env['PATH'] += ':' + self.bmaj_env['processdir']
      else:
        self.bmaj_env['PATH'] = self.bmaj_env['processdir']+':/usr/local/bin:/usr/sbin:/usr/bin'

      # Set some session specific env
      if self.bank.session is not None:
        self.bmaj_env['offlinedir'] = self.bank.session.get_offline_directory()
        self.bmaj_env['dirversion'] = self.bank.config.get('dir.version')
        self.bmaj_env['noextract'] = self.bank.config.get('no.extract')
        if self.bmaj_env['noextract'] is None:
          self.bmaj_env['noextract'] = ''
        self.bmaj_env['localrelease'] = self.bank.session.get_release_directory()
        if self.bank.session.get('release') is not None:
          self.bmaj_env['remoterelease'] = self.bank.session.get('release')
          self.bmaj_env['removedrelease'] = self.bank.session.get('release')

      for bdep in self.bank.depends:
        self.bmaj_env[bdep.name+'source'] = bdep.session.get_full_release_directory()


    def run(self):
      # Run meta processes
      self.global_status = True
      for meta in self.metas:
        if not self._stopevent.isSet():
          logging.info("PROC:META:RUN:"+meta)
          processes = self.bank.config.get(meta).split(',')
          processes_status = {}
          for bprocess in processes:
            # Process status already ok, do not replay
            if meta in self.meta_status and bprocess in self.meta_status[meta] and self.meta_status[meta][bprocess]:
              logging.info("PROC:META:SKIP:PROCESS:"+bprocess)
              processes_status[bprocess] = True
              continue
            logging.info("PROC:META:RUN:PROCESS:"+bprocess)
            name = self.bank.config.get(bprocess+'.name')
            desc = self.bank.config.get(bprocess+'.desc')
            cluster = self.bank.config.get(bprocess+'.cluster')
            proc_type = self.bank.config.get(bprocess+'.type')
            exe = self.bank.config.get(bprocess+'.exe')
            args = self.bank.config.get(bprocess+'.args')
            expand = self.bank.config.get_bool(bprocess+'.expand', default=True)
            bmaj_process = Process(meta+'_'+name, exe, args, desc, proc_type, cluster, expand, self.bmaj_env, os.path.dirname(self.bank.config.log_file))
            res = bmaj_process.run(self.simulate)
            processes_status[bprocess] = res
            if not res:
              self.global_status = False
              break
            if not self.simulate:
              self._get_metata_from_outputfile(bmaj_process.output_file)
        self.meta_status[meta] = processes_status

    def _get_metata_from_outputfile(self, output_file):
      '''
      Extract metadata given by process on stdout. Store metadata in self.metadata

      :param output_file: path to process output file
      :type output_file: str
      '''
      with open(output_file) as f:
        for line in f:
          if line.startswith('##BIOMAJ#'):
            line = line.replace('##BIOMAJ#', '')
            line = line.strip('\n\r')
            metas = line.split('#')
            meta_format = metas[0]
            meta_type = metas[1]
            meta_tags = metas[2]
            meta_files = metas[3]
            if not meta_format in self.meta_data:
              self.meta_data[meta_format] = []
            tags = meta_tags.split(',')
            tag_list = {}
            for tag in tags:
              t = tag.split(':')
              tag_list[t[0]] = t[1]
            self.meta_data[meta_format].append({'tags': tag_list,
                                                'types': meta_type.split(','),
                                                'files': meta_files.split(',')})

    def stop(self):
      self._stopevent.set( )
