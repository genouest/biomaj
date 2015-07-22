'''
Created on Feb 6, 2015

@author: tuco
'''
from ConfigParser import ConfigParser
from biomaj.manager.config import Config
from string import split
import json
from biomaj.manager.db.connector import BaseConnector
import os


class Bank:

    config = None
    global_config = None
    bank_config = None
    db = None

    def __init__(self, name=None, connect=False, file=None):

        # List of release loaded?
        self.has_releases = False
        # List of available releses
        self.available_releases = []
        self.removed_releases = []
        # Bank has a future_release available?
        self.future_releases = None

        if not name:
            raise Exception("A bank name is required!")
        self.name = name
        self.idbank = None
        # Bank has 2 config:
        # - global_config which refers to 'global.properties'
        # - config_bank which refers to '<bank>.properties'
        # Use Biomaj3 BiomajConfig config reader
        if file is not None:
            BiomajConfig.load_config(config_file=file)
        self.config = BiomajConfig(name)

        if connect:
            # Here we need to specify we want properties from global_config
            # as db.name also exists in <bank>.properties file (Bank name :( )
            self.db = BaseConnector(url=self.config.global_config.get('GENERAL','db.url'),
                                    db=self.config.global_config.get('GENERAL','db.name')).get_connector()
            self.idbank = self.db._check_bank(self.name)

    def history(self, to_json=False):
        '''
            Get the release history of a specific bank

            :param name: Name of the bank
            :type name: String
            :param idbank: Bank id (primary key)
            :type idbank: Integer
            :param to_json: Converts output to json
            :type name: Boolean (Default False)
            :return: A list with all the bank history
        '''
        return self.db._history(bank=self, to_json=to_json)

    def mongo_history(self):
        """
            Get the releases history of a bank from the database and build a Mongo like document in json
            :param name: Name of the bank
            :type name: String
            :param idbank: Bank id (primary key)
            :tpye idbank: Integer
            :return: Jsonified history + extra info to be included into bioweb (Institut Pasteur only)
        """
        return  self.db._mongo_history(bank=self)

    def formats(self, release='current', flat=False):
        '''
            Check the "supported formats" for a specific bank.
            This is done simpy by getting the name of subdirectory(ies)
            listed for the release checked (current|future_release)
            :param release: Release type to check (current[Default]|future)
            :type release: String
            :param flat: Get the list as a flat string [Default False]
            :type flat: Boolean
            :return: List of supported format(s)
        '''
        path = os.path.join(self.config.get('data.dir'), self.name, release)
        if not os.path.exists(path):
            raise Exception("Can't get format(s) from '%s', directory not found" % path)
        if flat:
            return ','.join(os.listdir(path))
        return os.listdir(path)


    def formats_as_string(self, release='current'):
        return self.formats(release=release, flat=True)

    def get_dict_sections(self, tool=None):
        '''
         Get the "supported" blast2/golden indexes for this bank
            Each bank can have some sub sections. This method return
            them as a dictionary

            :param tool: Name of the index to search
            :type tool: String
            :return: If info defined,
                     dictionary with section(s) and bank(s)
                     sorted by type(nuc/pro)
                     Otherwise empty dict
        '''
        if tool is None:
            raise Exception("A tool name is required to retrieve virtual info")

        ndbs = 'db.%s.nuc' % tool
        pdbs = 'db.%s.pro' % tool
        nsec = ndbs + '.sections'
        psec = pdbs + '.sections'
        dbs = {}

        if self.config.config_bank.has_option('GENERAL', ndbs):
            dbs['nuc'] = {'dbs': []}
            for sec in string.split(self.config.get(ndbs), ','):
                dbs['nuc']['dbs'].append(sec)
        if self.config.config_bank.has_option('GENERAL', pdbs):
            dbs['pro'] = {'dbs': []}
            for sec in string.split(self.config.get(pdbs), ','):
                dbs['pro']['dbs'].append(sec)
        if self.config.config_bank.has_option('GENERAL', nsec):
            if 'nuc' in dbs:
                dbs['nuc']['secs'] = []
            else:
                dbs['nuc': {'dbs': []}]
            for sec in string.split(self.config.get(nsec), ','):
                dbs['nuc']['secs'].append(sec)
        if self.config.config_bank.has_option('GENERAL', psec):
            if 'pro' in dbs:
                dbs['pro']['secs'] = []
            else:
                dbs['pro'] = {'secs': []}
            for sec in string.split(self.config.get(psec), ','):
                dbs['pro']['secs'].append(sec)

        if dbs.keys():
            if not len(self.available_releases):
                self.db._get_releases(self)
            dbs['inf'] = {'desc': self.config.get('db.fullname')
                          ,'vers': self.available_releases[0].release if len(self.available_releases) else ""
                          }
            dbs['tool'] = tool
        return dbs

    def get_list_sections(self, tool=None):
        '''
            Get the "supported" blast2/golden indexes for this bank
            Each bank can have some sub sections.

            :param tool: Name of the index to search
            :type tool: String
            :return: If info defined,
                     list of bank(s)/section(s) found
                     Otherwise empty list
        '''
        if tool is None:
            raise Exception("A tool name is required to retrieve virtual info")

        ndbs = 'db.%s.nuc' % tool
        pdbs = 'db.%s.pro' % tool
        nsec = ndbs + '.sections'
        psec = pdbs + '.sections'
        dbs = []

        if self.config.config_bank.has_option('GENERAL', ndbs):
            for sec in string.split(self.config.get(ndbs), ','):
                dbs.append(sec)
        if self.config.config_bank.has_option('GENERAL', pdbs):
            for sec in string.split(self.config.get(pdbs), ','):
                dbs.append(sec)
        if self.config.config_bank.has_option('GENERAL', nsec):
            for sec in string.split(self.config.get(nsec), ','):
                dbs.append(sec)
        if self.config.config_bank.has_option('GENERAL', psec):
            for sec in string.split(self.config.get(psec), ','):
                dbs.append(sec)

        return dbs

    def full_info(self):
        """
            Get more information about a bank
        """
        if not self.has_releases:
            self.db._load_releases()
        releases = self.available_releases
        releases.extend(self.removed_releases)
        for release in releases:
            release.info()
        return

    def has_formats(self, format=format):
        '''
            Checks wether the bank supports 'format' or not
            :param format: Format to check
            :type format: String
            :return: Boolean
        '''
        if not format:
            raise Exception("Format is required")
        fmts = self.formats()
        print "Formats: %s" % str(fmts)
        if format in fmts:
            return True
        return False

    def _get_formats_for_release(self, path):
        """
            Get all the formats supported for a bank (path).
            :param path: Path of the release to search in
            :type path: String (path)
            :return: List of formats
        """

        if not path:
            raise Exception("A path is required")
        if not os.path.exists(path):
            #raise Exception("Path %s does not exist" % path)
            print ("[WARNING] Path %s does not exist" % path)
            return []
        formats = []

        for dir, dirs, filenames in os.walk(path):
            if dir == path or not len(dirs):
                continue
            if dir == 'flat' or dir == 'uncompressed':
                continue
            for d in dirs:
                formats.append('@'.join(['prog', os.path.basename(dir), d or '-', '?']))
        return formats

    def __load_releases(self):
        """
            Search for all the available release for a particular bank
            It is based on the number of kept release (config: keep.old.version)
            Available release(s) are queried from the database
            :return: Int (0) if all ok
            :raise: Exception
        """

        if self.has_releases:
            return 0

        self.db._get_releases(self)
        return 0

    def __load_future_release(self):
        '''
            Load the release tagged has 'future' from the database. Those release are just release that have
            been build and are not published yet. We stopped the workflow before the 'deployement' stage.
            :return: Int
                     Raise Exception on error
        '''
        self.db._get_future_release(self)
        return 0

