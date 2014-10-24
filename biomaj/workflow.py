import logging
import datetime
import os

from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload
from biomaj.mongo_connector import MongoConnector

class Workflow:
  '''
  Bank update workflow
  '''

  FLOW_INIT = 'init'
  FLOW_CHECK = 'check'
  FLOW_DEPENDS = 'depends'
  FLOW_PREPROCESS = 'preprocess'
  FLOW_RELEASE = 'release'
  FLOW_DOWNLOAD = 'download'
  FLOW_POSTPROCESS = 'postprocess'
  FLOW_PUBLISH = 'publish'
  FLOW_OVER = 'over'

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, bank):
    '''
    Instantiate a new workflow

    :param bank: bank on which to apply the workflow
    :type bank: Bank
    '''
    self.bank = bank

  def get_flow(self, task):
    for flow in Workflow.FLOW:
      if flow['name'] == task:
        return flow

class UpdateWorkflow(Workflow):

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'depends', 'steps': []},
    { 'name': 'preprocess', 'steps': []},
    { 'name': 'release', 'steps': []},
    { 'name': 'download', 'steps': ['uncompress','copy']},
    { 'name': 'postprocess', 'steps': []},
    { 'name': 'publish', 'steps': ['clean_offline', 'delete_old']},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, bank):
    '''
    Instantiate a new workflow

    :param bank: bank on which to apply the workflow
    :type bank: Bank
    '''
    Workflow.__init__(self, bank)
    logging.debug('New workflow')
    self.bank = bank
    self.session = bank.session
    self.options = bank.options
    self.name = bank.name
    # Skip all remaining tasks, no need to update
    self.skip_all = False

  def start(self):
    '''
    Start the workflow
    '''
    logging.info('Start workflow')
    for flow in UpdateWorkflow.FLOW:

      if self.skip_all:
        continue

      if self.options and 'stop_before' in self.options and self.options['stop_before'] == flow['name']:
        break
      # Always run INIT
      if flow['name'] == Workflow.FLOW_INIT or not self.session.get_status(flow['name']):
        logging.info('Workflow:'+flow['name'])
        self.session._session['status'][flow['name']] = getattr(self, 'wf_'+flow['name'])()
        if flow['name'] != Workflow.FLOW_OVER and not self.session.get_status(flow['name']):
            logging.error('Error during task '+flow['name'])
            self.wf_over()
            return False
        # Main task is over, execute sub tasks of main
        for step in flow['steps']:
          res = getattr(self, 'wf_'+step)()
          if not res:
            logging.error('Error during '+flow['name']+' subtask: wf_' + step)
            return False
      if self.options and 'stop_after' in self.options and self.options['stop_after'] == flow['name']:
        break
    return True

  def wf_init(self):
    '''
    Initialize workflow
    '''
    logging.debug('Workflow:wf_init')
    self.session._session['update'] = True
    data_dir = self.session.config.get('data.dir')
    lock_file = os.path.join(data_dir,self.name+'.lock')
    if os.path.exists(lock_file):
      logging.error('Bank '+self.name+' is locked, a process may be in progress, else remove the lock file')
      print 'Bank '+self.name+' is locked, a process may be in progress, else remove the lock file'
      return False
    f = open(lock_file, 'w')
    f.write('1')
    f.close()
    return True

  def wf_check(self):
    '''
    Basic checks
    '''
    logging.debug('Workflow:wf_check')
    return True

  def wf_depends(self):
    '''
    Checks bank dependencies with other banks. If bank has dependencies, execute update on other banks first
    '''
    logging.debug('Workflow:wf_depends')
    return True

  def wf_preprocess(self):
    '''
    Execute pre-processes
    '''
    logging.debug('Workflow:wf_preprocess')
    return True

  def wf_release(self):
    '''
    Find current release on remote
    '''
    logging.debug('Workflow:wf_release')
    if self.session.config.get('release.file') == '':
      now = datetime.datetime.now()
      self.session._session['release'] = str(now.year)+'-'+str(now.month)+'-'+str(now.day)
    else:
      logging.warn('SHOULD GET RELEASE FROM release.file')
      logging.warn('IF SAME RELEASE SKIP')
      #self.skip_all = True
      #self.session._session['status'][Workflow.FLOW_OVER] = True
      #self.session._session['update'] = False
      raise Exception('GET RELEASE NOT YET IMPLEMENTED')
    logging.info('Session:Release:'+self.session._session['release'])
    return True

  def wf_download(self):
    '''
    Download remote files or use an available local copy from last production directory if possible.
    '''
    logging.debug('Workflow:wf_download')
    flow = self.get_flow(Workflow.FLOW_DOWNLOAD)
    downloader = None
    cf = self.session.config

    logging.warn('SHOULD DOWNLOAD FILES ACCORDING TO PROTOCOL')
    if cf.get('protocol') == 'ftp':
      downloader = FTPDownload('ftp', cf.get('server'), cf.get('remote.dir'))
    if downloader is None:
      logging.error('Protocol '+cf.get('protocol')+' not supported')
      return False

    (file_list, dir_list) = downloader.list()

    downloader.match(cf.get('remote.files').split(), file_list, dir_list)

    self.session._session['download_files'] = downloader.files_to_download

    logging.warn('SHOULD CHECK IF FILE NOT ALREADY PRESENT IN PRODUCTION')
    logging.warn('SHOULD CHECK IF FILE NOT ALREADY PRESENT IN OFFLINE DIR')
    self.banks = MongoConnector.banks
    self.bank = self.banks.find_one({'name': self.name},{ 'production': 1})

    nb_prod_dir = len(self.bank['production'])
    offline_dir = self.session.get_offline_directory()

    copied_files = []

    if nb_prod_dir > 0:
      # Get last production
      last_production = self.bank['production'][nb_prod_dir-1]
      # Get session corresponding to production directory
      last_production_session = self.banks.find_one({'name': self.name, 'sessions.id': last_production['session']},{ 'sessions.$': 1})
      last_production_dir = os.path.join(last_production['data_dir'],cf.get('dir.version'),last_production['release'])
      # Checks if some files can be copied instead of downloaded
      downloader.download_or_copy(last_production_session['sessions'][0]['files'],last_production_dir)
      #release_dir = os.path.join(self.session.config.get('data.dir'),
      #              self.session.config.get('dir.version'),
      #              self.session.get_release_directory())
      logging.debug('Workflow:wf_download:Copy files from '+last_production_dir)
      copied_files = downloader.files_to_copy
      Utils.copy_files(downloader.files_to_copy, offline_dir)

    self.downloaded_files = downloader.download(offline_dir) + copied_files

    downloader.close()

    return True

  def wf_uncompress(self):
    '''
    Uncompress files if archives and no.extract = false
    '''
    logging.debug('Workflow:wf_uncompress')
    no_extract = self.session.config.get('no.extract')
    if no_extract is None or no_extract == 'false':
      for file in self.downloaded_files:
        Utils.uncompress(self.session.get_offline_directory() + '/' + file['name'])
    return True

  def wf_copy(self):
    '''
    Copy files from offline directory to release directory
    '''
    logging.debug('Workflow:wf_copy')
    from_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('offline.dir.name'))
    regexp = self.session.config.get('local.files').split()
    to_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('dir.version'),
                  self.session.get_release_directory())

    local_files = Utils.copy_files_with_regexp(from_dir,to_dir,regexp, True)
    self.session._session['files'] = local_files
    if len(self.session._session['files']) == 0:
      logging.error('Workflow:wf_copy:No file match in offline dir')
      return False
    return True

  def wf_postprocess(self):
    '''
    Execute post processes
    '''
    logging.debug('Workflow:wf_postprocess')
    return True

  def wf_publish(self):
    '''
    Add *current* symlink to this release
    '''
    logging.debug('Workflow:wf_publish')
    current_link = os.path.join(self.session.config.get('data.dir'),
                                self.session.config.get('dir.version'),
                                'current')
    prod_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('dir.version'),
                  self.session.get_release_directory())
    to_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('dir.version'))

    if os.path.lexists(current_link):
      os.remove(current_link)
    os.chdir(to_dir)
    os.symlink(prod_dir,'current')
    return True

  def wf_clean_offline(self):
    '''
    Clean offline directory
    '''
    logging.debug('Workflow:wf_clean_offline')
    return True

  def wf_delete_old(self):
    '''
    Delete old production dirs
    '''
    logging.debug('Workflow:wf_delete_old')
    return True

  def wf_over(self):
    '''
    Workflow is over
    '''
    logging.debug('Workflow:wf_over')
    data_dir = self.session.config.get('data.dir')
    lock_file = os.path.join(data_dir,self.name+'.lock')
    os.remove(lock_file)
    return True
