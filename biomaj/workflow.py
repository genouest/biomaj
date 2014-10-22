import logging
import datetime

class Workflow:
  '''
  Bank update workflow
  '''

  FLOW_INIT = 'init'
  FLOW_CHECK = 'check'
  FLOW_PREPROCESS = 'preprocess'
  FLOW_RELEASE = 'release'
  FLOW_DOWNLOAD = 'download'
  FLOW_POSTPROCESS = 'postprocess'
  FLOW_PUBLISH = 'publish'
  FLOW_OVER = 'over'

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'preprocess', 'steps': []},
    { 'name': 'release', 'steps': []},
    { 'name': 'download', 'steps': []},
    { 'name': 'postprocess', 'steps': []},
    { 'name': 'publish', 'steps': []},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, session, options = None):
    logging.debug('New workflow')
    self.session = session
    self.options = options

  def start(self):
    logging.info('Start workflow')
    for flow in Workflow.FLOW:
      if self.options and 'stop_before' in self.options and self.options['stop_before'] == flow['name']:
        break
      if not self.session.get_status(flow['name']):
        logging.info('Workflow:'+flow['name'])
        self.session._session['status'][flow['name']] = getattr(self, 'wf_'+flow['name'])()
        if not self.session.get_status(flow['name']):
            logging.error('Error during task '+flow['name'])
            break
      if self.options and 'stop_after' in self.options and self.options['stop_after'] == flow['name']:
        break

  def wf_init(self):
      logging.debug('Workflow:wf_init')
      return True

  def wf_check(self):
      logging.debug('Workflow:wf_check')
      return True

  def wf_preprocess(self):
      logging.debug('Workflow:wf_preprocess')
      return True

  def wf_release(self):
      logging.debug('Workflow:wf_release')
      if self.session.config_bank.get('GENERAL','release.file') == '':
        now = datetime.datetime.now()
        self.session._session['release'] = str(now.year)+'-'+str(now.month)+'-'+str(now.day)
      else:
        logging.warn('SHOULD GET RELEASE FROM release.file')
        raise Exception('GET RELEASE NOT YET IMPLEMENTED')
      logging.info('Session:Release:'+self.session._session['release'])
      return True

  def wf_download(self):
      logging.debug('Workflow:wf_download')
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
