import logging
import datetime
import os

from biomaj.utils import Utils

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
  FLOW_END = 'end'

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'depends', 'steps': []},
    { 'name': 'preprocess', 'steps': []},
    { 'name': 'release', 'steps': []},
    { 'name': 'download', 'steps': ['uncompress','copy']},
    { 'name': 'postprocess', 'steps': []},
    { 'name': 'publish', 'steps': []},
    { 'name': 'over', 'steps': []},
    { 'name': 'end', 'steps': []}
  ]

  def get_flow(self, task):
    for flow in Workflow.FLOW:
      if flow['name'] == task:
        return flow

  def __init__(self, session, options = None):
    logging.debug('New workflow')
    self.session = session
    self.options = options
    self.name = None

  def start(self, name):
    logging.info('Start workflow')
    self.name = name
    for flow in Workflow.FLOW:
      if self.options and 'stop_before' in self.options and self.options['stop_before'] == flow['name']:
        break
      # Always run INIT
      if flow['name'] == Workflow.FLOW_INIT or not self.session.get_status(flow['name']):
        logging.info('Workflow:'+flow['name'])
        self.session._session['status'][flow['name']] = getattr(self, 'wf_'+flow['name'])()
        if flow['name'] != Workflow.FLOW_END and not self.session.get_status(flow['name']):
            logging.error('Error during task '+flow['name'])
            self.wf_end()
            return False
      if self.options and 'stop_after' in self.options and self.options['stop_after'] == flow['name']:
        break
    return True

  def wf_init(self):
      logging.debug('Workflow:wf_init')
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
      logging.debug('Workflow:wf_check')
      return True

  def wf_depends(self):
      logging.debug('Workflow:wf_depends')
      return True

  def wf_preprocess(self):
      logging.debug('Workflow:wf_preprocess')
      return True

  def wf_release(self):
      logging.debug('Workflow:wf_release')
      if self.session.config.get('release.file') == '':
        now = datetime.datetime.now()
        self.session._session['release'] = str(now.year)+'-'+str(now.month)+'-'+str(now.day)
      else:
        logging.warn('SHOULD GET RELEASE FROM release.file')
        raise Exception('GET RELEASE NOT YET IMPLEMENTED')
      logging.info('Session:Release:'+self.session._session['release'])
      return True

  def wf_download(self):
      logging.debug('Workflow:wf_download')
      flow = self.get_flow(Workflow.FLOW_DOWNLOAD)
      logging.warn('SHOULD DOWNLOAD FILES ACCORDING TO PROTOCOL')
      for step in flow['steps']:
        res = getattr(self, 'wf_'+step)()
        if not res:
          logging.error('Error during subtask: wf_' + step)
          return False
      return True

  def wf_uncompress(self):
      logging.debug('Workflow:wf_uncompress')
      no_extract = self.session.config.get('no.extract')
      if no_extract is not None and no_extract == 'false':
        for file in self.session._session['files']:
          Utils.uncompress(file['name'])
      return True

  def wf_copy(self):
      logging.debug('Workflow:wf_copy')
      from_dir = os.path.join(self.session.config.get('data.dir'),
                    self.session.config.get('offline.dir.name'))
      regexp = self.session.config.get('local.files').split()
      to_dir = os.path.join(self.session.config.get('data.dir'),
                    self.session.config.get('dir.version'),
                    self.session.get_release_directory())

      self.session._session['files'] = Utils.copy_files_with_regexp(from_dir,to_dir,regexp, True)
      return True

  def wf_postprocess(self):
      logging.debug('Workflow:wf_postprocess')
      return True

  def wf_publish(self):
      logging.debug('Workflow:wf_publish')
      return True

  def wf_over(self):
      logging.debug('Workflow:wf_over')
      return True

  def wf_end(self):
      logging.debug('Workflow:wf_end')
      data_dir = self.session.config.get('data.dir')
      lock_file = os.path.join(data_dir,self.name+'.lock')
      os.remove(lock_file)
      return True
