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
    """

    def __init__(self, name=None, prop_dir=None):

        #  We set 'config (3.0)' instaed of 'conf (1.2.3)' as the properties does not change in syntax
        if prop_dir:
            self.prop_dir = prop_dir
        # Try to get global.properties from ENV
        elif 'BIOMAJ_ROOT' in os.environ:
            self.prop_dir = os.path.join(os.environ['BIOMAJ_ROOT'])
        else:
            raise Exception("BIOMAJ_ROOT not set and not prop_dir defined!")

        cfg_list = []
        if os.path.isdir(self.prop_dir):
            self.global_file = os.path.join(self.prop_dir, self.global_file)
            if not os.path.isfile(self.global_file):
                raise Exception("global.properties not found in %s!" % self.prop_dir)
            else:
                cfg_list.append(self.global_file)
                # self.global_cfg = ConfigParser.ConfigParser()
                # self.global_cfg.read([self.global_file])
        else:
            raise Exception("Properties directory %s not found" % self.prop_dir)

        if name:
            # Try to read 'bank' properties file
            self.bank_file = os.path.join(self.prop_dir, 'config', name + '.properties')
            if not os.path.isfile(self.bank_file):
                raise Exception("Can't find %s.properties" % os.path.join(self.prop_dir, 'config', name))
            cfg_list.append(self.bank_file)
            # self.bank_cfg = ConfigParser.ConfigParser()
            # self.bank_cfg.read([self.bank_file])
        self.config = ConfigParser()
        self.config.read(cfg_list)

        return None

    def get(self, key, section='GENERAL'):
        if not key:
            raise Exception("No key to search")
        try:
            return self.config.get(section, key)
        except (NoOptionError, KeyError) as e:
            raise e

