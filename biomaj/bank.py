import os
import ConfigParser
import logging

from biomaj.mongo_connector import MongoConnector

from biomaj.session import Session
from biomaj.workflow import Workflow


class Bank:
  '''
  BioMAJ bank

  TODO: define options:
     - stop_before, stop_after: stop before/after processing a workflow task

  '''

  config = None

  @staticmethod
  def load_config(config_file='global.properties'):
    '''
    Loads general config

    :param config_file: global.properties file path
    :type config_file: str
    '''
    if not os.path.exists(config_file) and not os.path.exists(os.path.expanduser('~/.biomaj.cfg')):
      raise Exception('Missing configuration file')
    Bank.config = ConfigParser.ConfigParser()
    Bank.config.read([config_file, os.path.expanduser('~/.biomaj.cfg')])


  def __init__(self, name, options={}):
    '''
    Get a bank from db or creates a new one

    :param name: name of the bank, must match its config file
    :type name: str
    :param options: bank options
    :type options: dict
    '''
    logging.debug('Initialize '+name)
    if Bank.config is None:
      raise Exception('Configuration must be loaded first')

    self.options = options
    if MongoConnector.db is None:
      MongoConnector(Bank.config.get('GENERAL','db.url'),
                      Bank.config.get('GENERAL','db.name'))
    self.banks = MongoConnector.banks

    self.name = name
    self.config_bank = ConfigParser.ConfigParser()
    conf_dir = Bank.config.get('GENERAL', 'conf.dir')
    self.config_bank.read([os.path.join(conf_dir,name+'.properties')])
    self.bank = self.banks.find_one({'name': self.name})
    if self.bank is None:
        self.bank = { 'name' : self.name, 'sessions': [] }
        self.banks.insert(self.bank)

  def controls(self):
    '''
    Initial controls (create directories etc...)
    '''
    data_dir = Bank.config.get('GENERAL','data.dir')
    bank_dir = self.config_bank.get('GENERAL','dir.version')
    bank_dir = os.path.join(data_dir,bank_dir)
    if not os.path.exists(bank_dir):
      os.makedirs(bank_dir)

    offline_dir = self.config_bank.get('GENERAL','offline.dir.name')
    offline_dir = os.path.join(data_dir,offline_dir)
    if not os.path.exists(offline_dir):
      os.makedirs(offline_dir)

    log_dir = Bank.config.get('GENERAL','log.dir')
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
    self.banks.update({'_id': self.bank['_id']}, {'$push' : { 'sessions': self.session._session }})

  def load_session(self):
    '''
    Loads last session or, if over or forced, a new session
    '''
    if len(self.bank['sessions']) == 0 or 'fromscratch' in self.options:
        self.session = Session(Bank.config, self.config_bank)
        logging.debug('Start new session')
    else:
        # Take last session
        self.session = Session(Bank.config, self.config_bank)
        self.session.load(self.bank['sessions'][len(self.bank['sessions'])-1])
        if self.session.get_status(Workflow.FLOW_OVER):
          self.session = Session(Bank.config, self.config_bank)
          logging.debug('Start new session')
        else:
          logging.debug('Load previous session '+str(self.session.get('id')))

  def update(self):
    '''
    Launch a bank update
    '''
    logging.warning('UPDATE BANK: '+self.name)
    self.controls()
    self.load_session()
    self.start_update()

  def start_update(self):
    '''
    Start an update workflow
    '''
    workflow = Workflow(self.session, self.options)
    workflow.start()
    return
