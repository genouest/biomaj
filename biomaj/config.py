import logging
import os
import ConfigParser

class BiomajConfig:
  '''
  Manage Biomaj configuration
  '''


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


  def get(self, prop, section='GENERAL'):
    '''
    Get a property from bank or general configration. Optionally in section.
    '''
    if self.config_bank.has_option(section,prop):
      val = self.config_bank.get(section,prop)
      # If regexp, escape backslashes
      if prop == 'local.files' or prop == 'remote.files':
        val = val.replace('\\\\','\\')
      return val

    if BiomajConfig.global_config.has_option(section, prop):
      return BiomajConfig.global_config.get(section, prop)

    return None
