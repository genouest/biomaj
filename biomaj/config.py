import logging
import logging.config
import os
import ConfigParser
import time

class BiomajConfig:
  '''
  Manage Biomaj configuration
  '''

  DEFAULTS = {
  'http.parse.dir.line': r'<a[\s]+href="([\S]+)/".*alt="\[DIR\]">.*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})',
  'http.parse.file.line': r'<a[\s]+href="([\S]+)".*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})[\s]+([\d\.]+[MKG]{0,1})',
  'http.group.dir.name': 1,
  'http.group.dir.date': 2,
  'http.group.file.name': 1,
  'http.group.file.date': 2,
  'http.group.file.size': 3
  }

  '''
  Global configuration file
  '''
  global_config = None

  @staticmethod
  def load_config(config_file='global.properties'):
    '''
    Loads general config

    :param config_file: global.properties file path
    :type config_file: str
    '''
    if not os.path.exists(config_file) and not os.path.exists(os.path.expanduser('~/.biomaj.cfg')):
      raise Exception('Missing global configuration file')

    BiomajConfig.config_file = config_file

    BiomajConfig.global_config = ConfigParser.ConfigParser()
    BiomajConfig.global_config.read([config_file, os.path.expanduser('~/.biomaj.cfg')])


  def __init__(self, bank):
    '''
    Loads bank configuration

    :param bank: bank name
    :type bank: str
    '''
    self.name = bank
    if BiomajConfig.global_config is None:
      BiomajConfig.load_config()
    self.config_bank = ConfigParser.ConfigParser()
    conf_dir = BiomajConfig.global_config.get('GENERAL', 'conf.dir')
    if not os.path.exists(os.path.join(conf_dir,bank+'.properties')):
      logging.error('Bank configuration file does not exists')
      raise Exception('Configuration file '+bank+'.properties does not exists')

    self.config_bank.read([os.path.join(conf_dir,bank+'.properties')])
    self.last_modified = long(os.stat(os.path.join(conf_dir,bank+'.properties')).st_mtime)

    if os.path.exists(os.path.expanduser('~/.biomaj.cfg')):
      logging.config.fileConfig(os.path.expanduser('~/.biomaj.cfg'))
    else:
      logging.config.fileConfig(BiomajConfig.config_file)

    logger = logging.getLogger()
    bank_log_dir = os.path.join(self.get('log.dir'),bank,str(time.time()))
    if not os.path.exists(bank_log_dir):
      os.makedirs(bank_log_dir)
    hdlr = logging.FileHandler(os.path.join(bank_log_dir,bank+'.log'))
    #hdlr.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)-5.5s [%(name)s][%(threadName)s] %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)


  def get(self, prop, section='GENERAL', escape=True):
    '''
    Get a property from bank or general configration. Optionally in section.
    '''
    if self.config_bank.has_option(section,prop):
      val = self.config_bank.get(section,prop)
      # If regexp, escape backslashes
      if escape and prop == 'local.files' or prop == 'remote.files':
        val = val.replace('\\\\','\\')
      return val

    if BiomajConfig.global_config.has_option(section, prop):
      return BiomajConfig.global_config.get(section, prop)

    if prop in BiomajConfig.DEFAULTS:
      return BiomajConfig.DEFAULTS[prop]

    return None



  def get_time(self):
    '''
    Return last modification time of config files
    '''
    return self.last_modified
