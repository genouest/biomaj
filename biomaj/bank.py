import os
import logging

from biomaj.mongo_connector import MongoConnector

from biomaj.session import Session
from biomaj.workflow import UpdateWorkflow, Workflow
from biomaj.config import BiomajConfig
from biomaj.options import Options

from bson.objectid import ObjectId

class Bank:
  '''
  BioMAJ bank
  '''

  def __init__(self, name, options=None):
    '''
    Get a bank from db or creates a new one

    :param name: name of the bank, must match its config file
    :type name: str
    :param options: bank options
    :type options: argparse
    '''
    logging.debug('Initialize '+name)
    if BiomajConfig.global_config is None:
      raise Exception('Configuration must be loaded first')

    self.name = name

    self.config = BiomajConfig(self.name)

    self.options = Options(options)

    if MongoConnector.db is None:
      MongoConnector(BiomajConfig.global_config.get('GENERAL','db.url'),
                      BiomajConfig.global_config.get('GENERAL','db.name'))

    self.banks = MongoConnector.banks

    self.bank = self.banks.find_one({'name': self.name})

    if self.bank is None:
        self.bank = { 'name' : self.name, 'sessions': [], 'production': [], 'type': self.config.get('db.type') }
        self.bank['_id'] = self.banks.insert(self.bank)

    self.session = None
    self.use_last_session = False

  @staticmethod
  def list(with_sessions=False):
    '''
    Return a list of banks

    :param with_sessions: should sessions be returned or not (can be quite big)
    :type with_sessions: bool
    :return: list of :class:`biomaj.bank.Bank`
    '''
    if MongoConnector.db is None:
      MongoConnector(BiomajConfig.global_config.get('GENERAL','db.url'),
                      BiomajConfig.global_config.get('GENERAL','db.name'))


    if with_sessions:
      return MongoConnector.banks.find({})
    else:
      return MongoConnector.banks.find({},{'sessions': 0})

  def controls(self):
    '''
    Initial controls (create directories etc...)
    '''
    data_dir = self.config.get('data.dir')
    bank_dir = self.config.get('dir.version')
    bank_dir = os.path.join(data_dir,bank_dir)
    if not os.path.exists(bank_dir):
      os.makedirs(bank_dir)

    offline_dir = self.config.get('offline.dir.name')
    offline_dir = os.path.join(data_dir,offline_dir)
    if not os.path.exists(offline_dir):
      os.makedirs(offline_dir)

    log_dir = self.config.get('log.dir')
    log_dir = os.path.join(log_dir,self.name)
    if not os.path.exists(log_dir):
      os.makedirs(log_dir)


  def delete(self):
    '''
    Delete bank from database, not files
    '''
    self.banks.remove({'_id': self.bank['_id']})

  def save_session(self):
    '''
    Save session in database
    '''
    if self.use_last_session:
      # Remove last session
      self.banks.update({'name': self.name}, {'$pull' : { 'sessions.id': self.session._session['id'] }})
    # Insert session
    self.banks.update({'name': self.name}, {'$push' : { 'sessions': self.session._session }})
    if self.session.get_status(Workflow.FLOW_OVER):
      logging.debug('Bank:Save:'+self.name)
      if len(self.bank['production']) > 0:
        # Remove from database
        self.banks.update({'name': self.name}, {'$pull' : { 'production.release': self.session._session['release'] }})
        # Update local object
        #index = 0
        #for prod in self.bank['production']:
        #  if prod['release'] == self.session._session['release']:
        #    break;
        #  index += 1
        #if index < len(self.bank['production']):
        #  self.bank['production'].pop(index)

      production = { 'release': self.session.get('release'),
                      'session': self.session._session['id'],
                      'data_dir': self.config.get('data.dir'),
                      'prod_dir': self.session.get_release_directory()}

      self.bank['production'].append(production)
      if self.options.get_option(Options.PUBLISH):
        # If we want to publish, set as latest
        #self.bank['current'] = self.session._session['id']
        self.banks.update({'name': self.name},
                          {
                          '$push': {'production': production},
                          '$set': {'current': self.session._session['id']}
                          })
      else:
        # no publish, latest is not modified
        self.banks.update({'name': self.name},
                          {'$push': { 'production': production }})

      self.bank = self.banks.find_one({'name': self.name})

  def load_session(self, flow=Workflow.FLOW):
    '''
    Loads last session or, if over or forced, a new session

    Creates a new session or load last session if not over

    :param flow: kind of workflow
    :type flow: :func:`biomaj.workflow.Workflow.FLOW`
    '''
    if len(self.bank['sessions']) == 0 or self.options.get_option(Options.FROMSCRATCH):
        self.session = Session(self.name, self.config, flow)
        logging.debug('Start new session')
    else:
        # Take last session
        self.session = Session(self.name, self.config, flow)
        self.session.load(self.bank['sessions'][len(self.bank['sessions'])-1])
        if self.config.last_modified > self.session.get('last_modified'):
          # Config has changed, need to restart
          self.session = Session(self.name, self.config, flow)
          logging.info('Configuration file has been modified since last session, restart in any case a new session')
        if self.session.get_status(Workflow.FLOW_OVER):
          self.session = Session(self.name, self.config, flow)
          logging.debug('Start new session')
        else:
          logging.debug('Load previous session '+str(self.session.get('id')))
          self.use_last_session = True

  def update(self):
    '''
    Launch a bank update
    '''
    logging.warning('UPDATE BANK: '+self.name)
    self.controls()
    self.load_session(UpdateWorkflow.FLOW)
    res = self.start_update()
    self.save_session()
    return res

  def start_update(self):
    '''
    Start an update workflow
    '''
    workflow = UpdateWorkflow(self)
    return workflow.start()
