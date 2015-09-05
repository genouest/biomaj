from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import object
import logging
import logging.config
import os
import configparser
import time
import sys

from biomaj.bmajindex import BmajIndex

class BiomajConfig(object):
    '''
    Manage Biomaj configuration
    '''

    DEFAULTS = {
    'http.parse.dir.line': r'<img[\s]+src="[\S]+"[\s]+alt="\[DIR\]"[\s]*/?>[\s]*<a[\s]+href="([\S]+)/"[\s]*>.*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})',
    'http.parse.file.line': r'<img[\s]+src="[\S]+"[\s]+alt="\[[\s]+\]"[\s]*/?>[\s]<a[\s]+href="([\S]+)".*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})[\s]+([\d\.]+[MKG]{0,1})',
    'http.group.dir.name': 1,
    'http.group.dir.date': 2,
    'http.group.file.name': 1,
    'http.group.file.date': 2,
    'http.group.file.size': 3,
    'visibility.default': 'public',
    'historic.logfile.level': 'INFO',
    'bank.num.threads': 2,
    'files.num.threads': 4,
    'use_elastic': 0,
    'use_drmaa': 0,
    'db.type': '',
    'db.formats': '',
    'keep.old.version': 1,
    'docker.sudo': '1',
    'auto_publish': 0
    }

    # Old biomaj level compatibility
    LOGLEVEL = {
      'DEBUG': logging.DEBUG,
      'VERBOSE': logging.INFO,
      'INFO': logging.INFO,
      'WARN': logging.WARNING,
      'ERR': logging.ERROR
    }

    '''
    Global configuration file
    '''
    global_config = None

    '''
    Per use global configuration file, overriding global_config
    '''
    user_config = None

    @staticmethod
    def load_config(config_file=None, allow_user_config=True):
        '''
        Loads general config

        :param config_file: global.properties file path
        :type config_file: str
        :param allow_user_config: use ~/.biomaj.cfg if present
        :type allow_user_config: bool
        '''
        if config_file is None:
            env_file = os.environ.get('BIOMAJ_CONF')
            if env_file is not None and os.path.exists(env_file):
                config_file = env_file
            else:
                env_file = 'global.properties'
                if os.path.exists(env_file):
                    config_file = env_file

        if config_file is None or not os.path.exists(config_file):
            raise Exception('Missing global configuration file')

        BiomajConfig.config_file = os.path.abspath(config_file)

        BiomajConfig.global_config = configparser.ConfigParser()

        if allow_user_config and os.path.exists(os.path.expanduser('~/.biomaj.cfg')):
            BiomajConfig.user_config_file = os.path.expanduser('~/.biomaj.cfg')
            BiomajConfig.user_config = configparser.ConfigParser()
            BiomajConfig.user_config.read([os.path.expanduser('~/.biomaj.cfg')])
        else:
            BiomajConfig.user_config_file = None

        BiomajConfig.global_config.read([config_file])

        # ElasticSearch indexation support
        do_index = False
        if BiomajConfig.global_config.get('GENERAL', 'use_elastic') and \
          BiomajConfig.global_config.get('GENERAL', 'use_elastic') == "1":
            do_index = True
        if do_index:
            if BiomajConfig.global_config.get('GENERAL', 'elastic_nodes'):
                elastic_hosts = BiomajConfig.global_config.get('GENERAL', 'elastic_nodes').split(',')
            else:
                elastic_hosts = ['localhost']
            elastic_index = BiomajConfig.global_config.get('GENERAL', 'elastic_index')
            if elastic_index is None:
                elastic_index = 'biomaj'

            if BiomajConfig.global_config.has_option('GENERAL', 'test') and \
                BiomajConfig.global_config.get('GENERAL', 'test') == "1":
                # Test connection to elasticsearch, if not available skip indexing for tests
                BmajIndex.skip_if_failure = True


            BmajIndex.load(index=elastic_index, hosts=elastic_hosts,
                                                    do_index=do_index)




    def __init__(self, bank, options=None):
        '''
        Loads bank configuration

        :param bank: bank name
        :type bank: str
        :param options: bank options
        :type options: argparse
        '''
        self.name = bank
        if BiomajConfig.global_config is None:
            BiomajConfig.load_config()
        self.config_bank = configparser.ConfigParser()
        conf_dir = BiomajConfig.global_config.get('GENERAL', 'conf.dir')
        if not os.path.exists(os.path.join(conf_dir, bank+'.properties')):
            logging.error('Bank configuration file does not exists')
            raise Exception('Configuration file '+bank+'.properties does not exists')
        try:
            config_files = [BiomajConfig.config_file]
            if BiomajConfig.user_config_file is not None:
                config_files.append(BiomajConfig.user_config_file)
            config_files.append(os.path.join(conf_dir, bank+'.properties'))
            self.config_bank.read(config_files)
        except Exception as e:
            print("Configuration file error: "+str(e))
            logging.error("Configuration file error "+str(e))
            sys.exit(1)

        self.last_modified = int(os.stat(os.path.join(conf_dir, bank+'.properties')).st_mtime)

        if os.path.exists(os.path.expanduser('~/.biomaj.cfg')):
            logging.config.fileConfig(os.path.expanduser('~/.biomaj.cfg'))
        else:
            logging.config.fileConfig(BiomajConfig.config_file)

        do_log = False
        if options is None:
            do_log = True
        elif hasattr(options, 'no_log') and not options.no_log:
            do_log = True
        elif type(options) is dict and 'no_log' in options and not options['no_log']:
            do_log = True

        #if options is None or (( hasattr(options,'no_log') and not options.no_log) or ('no_log' in options and not options['no_log'])):
        if do_log:
            logger = logging.getLogger()
            bank_log_dir = os.path.join(self.get('log.dir'), bank, str(time.time()))
            if not os.path.exists(bank_log_dir):
                os.makedirs(bank_log_dir)
            hdlr = logging.FileHandler(os.path.join(bank_log_dir, bank+'.log'))
            self.log_file = os.path.join(bank_log_dir, bank+'.log')
            if options is not None and options.get_option('log') is not None:
                hdlr.setLevel(BiomajConfig.LOGLEVEL[options.get_option('log')])
            else:
                hdlr.setLevel(BiomajConfig.LOGLEVEL[self.get('historic.logfile.level')])
            formatter = logging.Formatter('%(asctime)s %(levelname)-5.5s [%(name)s][%(threadName)s] %(message)s')
            hdlr.setFormatter(formatter)
            logger.addHandler(hdlr)
        else:
            self.log_file = 'none'


    def set(self, prop, value, section='GENERAL'):
        self.config_bank.set(section, prop, value)

    def get_bool(self, prop, section='GENERAL', escape=True, default=None):
        '''
        Get a boolean property from bank or general configration. Optionally in section.
        '''
        value = self.get(prop, section, escape, default)
        if value is None:
            return False
        if value is True or value == 'true' or value == '1':
            return True
        else:
            return False

    def get(self, prop, section='GENERAL', escape=True, default=None):
        '''
        Get a property from bank or general configration. Optionally in section.
        '''
        # Compatibility fields
        if prop == 'depends':
            depend = self.get('db.source', section, escape, None)
            if depend:
                return depend

        if self.config_bank.has_option(section, prop):
            val = self.config_bank.get(section, prop)
            if prop == 'remote.dir' and not val.endswith('/'):
                val = val + '/'
            # If regexp, escape backslashes
            if escape and (prop == 'local.files' or prop == 'remote.files' or prop == 'http.parse.dir.line' or prop == 'http.parse.file.line'):
                val = val.replace('\\\\', '\\')
            return val

        if BiomajConfig.user_config is not None:
            if BiomajConfig.user_config.has_option(section, prop):
                return BiomajConfig.user_config.get(section, prop)

        if BiomajConfig.global_config.has_option(section, prop):
            return BiomajConfig.global_config.get(section, prop)

        if prop in BiomajConfig.DEFAULTS:
            return BiomajConfig.DEFAULTS[prop]

        return default


    def get_time(self):
        '''
        Return last modification time of config files
        '''
        return self.last_modified



    def check(self):
        '''
        Check configuration
        '''
        status = True
        if not self.get('data.dir'):
            logging.error('data.dir is not set')
            status = False
        if not self.get('conf.dir'):
            logging.error('conf.dir is not set')
            status = False
        if not self.get('log.dir'):
            logging.error('log.dir is not set')
            status = False
        if not self.get('process.dir'):
            logging.error('process.dir is not set')
            status = False
        if not self.get('db.fullname'):
            logging.warn('db.fullname is not set')
        if not self.get('db.formats'):
            logging.warn('db.formats is not set')
        if self.get('use_ldap'):
            if not self.get('ldap.host') or not self.get('ldap.port') or not self.get('ldap.dn'):
                logging.error('use_ldap set to 1 but missing configuration')
                status = False
        if self.get('use_elastic'):
            if not self.get('elastic_nodes') or not self.get('elastic_index'):
                logging.error('use_elastic set to 1 but missing configuration')
                status = False

        if not self.get('celery.queue') or not self.get('celery.broker'):
            logging.warn('celery config is not set, that\'s fine if you do not use Celery for background tasks')

        if not self.get('mail.smtp.host'):
            logging.error('SMTP mail config not set, you will not be able to send emails')
            status = False
        if self.get('mail.smtp.host') and not self.get('mail.from'):
            logging.error('Mail origin mail.from not set')
            status = False

        if not self.get('offline.dir.name'):
            logging.error('offline.dir.name is not set')
            status = False
        elif self.get('offline.dir.name').startswith('/'):
            logging.error('offline dir must be relative to data.dir and should not start with a /')
            status = False
        if not self.get('dir.version'):
            logging.error('dir.version is not set')
            status = False
        elif self.get('dir.version').startswith('/'):
            logging.error('dir.version must be relative to data.dir and should not start with a /')
            status = False
        if not self.get('protocol'):
            logging.error('protocol is not set')
            status = False
        else:
            protocol = self.get('protocol')
            allowed_protocols = ['multi', 'local', 'ftp', 'sftp', 'http', 'directftp', 'directhttp']
            if protocol not in allowed_protocols:
                logging.error('Protocol not supported: '+protocol)
                status = False
            if protocol != 'multi':
                if protocol != 'local' and not self.get('server'):
                    logging.error('server not set')
                    status = False
                if not self.get('remote.dir'):
                    logging.error('remote.dir not set')
                    status = False
                elif not self.get('remote.dir').endswith('/'):
                    logging.error('remote.dir must end with a /')
                    return False
                if not self.get('remote.files'):
                    logging.error('remote.files not set')
                    status = False
        if not self.get('local.files'):
            logging.error('local.files is not set')
            status = False
        # Remove processes
        processes = ['db.remove.process', 'db.pre.process']
        for process in processes:
            if self.get(process):
                metas = self.get(process).split(',')
                for meta in metas:
                    if not self.get(meta):
                        logging.error('Metaprocess ' + meta + ' not defined')
                        status = False
                    else:
                        procs = self.get(meta).split(',')
                        for proc in procs:
                            if not self.get(proc+'.name'):
                                logging.error('Process '+proc+' not defined')
                                status = False
                            else:
                                if not self.get(proc+'.exe'):
                                    logging.error('Process exe for '+proc+' not defined')
                                    status = False
        # Check blocks
        if self.get('BLOCKS'):
            blocks = self.get('BLOCKS').split(',')
            for block in blocks:
                if not self.get(block+'.db.post.process'):
                    logging.error('Block '+block+' not defined')
                    status = False
                else:
                    metas = self.get(block+'.db.post.process').split(',')
                    for meta in metas:
                        if not self.get(meta):
                            logging.error('Metaprocess ' + meta + ' not defined')
                            status = False
                        else:
                            procs = self.get(meta).split(',')
                            for proc in procs:
                                if not self.get(proc+'.name'):
                                    logging.error('Process '+proc+' not defined')
                                    status = False
                                else:
                                    if not self.get(proc+'.exe'):
                                        logging.error('Process exe for '+proc+' not defined')
                                        status = False
        return status
