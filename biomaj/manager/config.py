'''
Created on Feb 6, 2015

@author: tuco
'''


from ConfigParser import ConfigParser, NoOptionError
import os


class Config:

    global_file = 'global.properties'
    bank_file = None
    prop_dir = None
    config = None

    """
    Get configuration for a bank. It first reads global.properties then, if a name is given,
    overwrite default values with 'name'.properties

    :param name: Bank name (optional)
    :type name: Str
    :param prop_dir: Config properties directory
    :type prop_dir: Str (path)
    :param user: Bank user name (Biomaj 1.x)
    :type user: Str
    """
    def __init__(self, name=None, prop_dir=None, user=None):

        if user is None:
            user = os.getlogin()
        #  We set 'config (3.0)' instaed of 'conf (1.2.3)' as the properties does not change in syntax
        if prop_dir:
            Config.prop_dir = prop_dir
        # Try to get global.properties from ENV
        elif 'BIOMAJ_CONF' in os.environ:
            Config.prop_dir = os.path.join(os.environ['BIOMAJ_CONF'])
        # Backward compatibility with Biomaj 1.x
        elif 'BIOMAJ_ROOT' in os.environ:
            Config.prop_dir = os.path.join(os.environ['BIOMAJ_ROOT'], 'conf', 'db_properties', user)
        else:
            raise Exception("BIOMAJ_CONF not set and not prop_dir defined!")

        cfg_list = []
        if os.path.isdir(Config.prop_dir):
            Config.global_file = os.path.join(Config.prop_dir, Config.global_file)
            if not os.path.isfile(Config.global_file):
                raise Exception("global.properties not found in %s!" % Config.prop_dir)
            else:
                cfg_list.append(Config.global_file)
        else:
            raise Exception("Properties directory %s not found" % Config.prop_dir)

        if name:
            # Try to read 'bank' properties file
            Config.bank_file = os.path.join(Config.prop_dir, name + '.properties')
            if not os.path.isfile(Config.bank_file):
                raise Exception("Can't find %s.properties" % Config.bank_file)
            cfg_list.append(Config.bank_file)
        Config.config = ConfigParser()
        Config.config.read(cfg_list)

    def get(self, key=None, section='GENERAL'):
        '''
            Get a specific key from the configuration (global/bank)
            :param key: Key to retrieve
            :type key: String
            :param section: Section to search (default 'GENERAL')
            :type section: String
            :return: Value for key requested.
                    Raises NoOptionError if key not found
                    Raises Exception if no key provided
        '''
        if not key:
            raise Exception("No key to search")
        try:
            return self.config.get(section, key)
        except (NoOptionError, KeyError) as e:
            raise e

    def getint(self, key=None, section='GENERAL'):
        '''
            Get a specific key from the configuration (global/bank)
            :param key: Key to retrieve
            :type key: String
            :param section: Section to search (default 'GENERAL')
            :type section: String
            :return: Value for key requested.
                    Raises NoOptionError if key not found
                    Raises Exception if no key provided
        '''
        if not key:
            raise Exception("No key to search")
        try:
            return self.config.getint(section, key)
        except (NoOptionError, KeyError) as e:
            raise e

    def has_option(self, key=None, section='GENERAL'):
        '''
            Check if a key is present in the config (global/bank)
            :param key: Key to check
            :type key: String
            :param section: Section to search in (default 'GENERAL')
            :type section: String
            :return: Boolean True/False
                     Raises Exception if no key provided
        '''
        if not key:
            raise Exception("No key to search")
        return self.config.has_option(section, key)

