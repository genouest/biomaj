import os
import logging

from biomaj.mongo_connector import MongoConnector

from biomaj.session import Session
from biomaj.workflow import Workflow
from biomaj.config import BiomajConfig

from bson.objectid import ObjectId

class Bank:
  '''
  BioMAJ bank

  TODO: define options:
     - stop_before, stop_after: stop before/after processing a workflow task

  '''

  def __init__(self, name, options={}):
    '''
    Get a bank from db or creates a new one

    :param name: name of the bank, must match its config file
    :type name: str
    :param options: bank options
    :type options: dict
    '''
    logging.debug('Initialize '+name)
    if BiomajConfig.global_config is None:
      raise Exception('Configuration must be loaded first')

    self.name = name

    self.config = BiomajConfig(self.name)

    self.options = options

    if MongoConnector.db is None:
      MongoConnector(self.config.get('db.url'),
                      self.config.get('db.name'))
    self.banks = MongoConnector.banks

    self.bank = self.banks.find_one({'name': self.name})
    if self.bank is None:
        self.bank = { 'name' : self.name, 'sessions': [], 'production': [] }
        self.bank['_id'] = self.banks.insert(self.bank)

    self.session = None
    self.use_last_session = False

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
      self.banks.update({'name': self.name}, {'$pull' : { 'sessions.id': self.session._session.id }})
    # Insert session
    self.banks.update({'name': self.name}, {'$push' : { 'sessions': self.session._session }})

  def load_session(self):
    '''
    Loads last session or, if over or forced, a new session
    '''
    logging.error(self.bank)
    if len(self.bank['sessions']) == 0 or 'fromscratch' in self.options:
        self.session = Session(self.name, self.config)
        logging.debug('Start new session')
    else:
        # Take last session
        self.session = Session(self.name, self.config)
        self.session.load(self.bank['sessions'][len(self.bank['sessions'])-1])
        if self.session.get_status(Workflow.FLOW_OVER):
          self.session = Session(self.name, self.config)
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
    self.load_session()
    res = self.start_update()
    self.save_session()
    return res

  def start_update(self):
    '''
    Start an update workflow
    '''
    workflow = Workflow(self.session, self.options)
    return workflow.start(self.name)
