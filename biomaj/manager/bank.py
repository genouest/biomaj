'''
Created on Feb 6, 2015

@author: tuco
'''
from ConfigParser import ConfigParser
# import MySQLdb
from biomaj.manager.config import Config
from biomaj.manager.db.connector import Connector
from string import split
from _bsddb import DBSecondaryBadError

class Bank:

    config = None
    db = None

    def __init__(self, name=None, connect=True):

        if not name:
            raise Exception("A bank name is required!")
        if self.config is None:
            self.config = Config(name)
        if connect:
            self.db = Connector(self.config.get('db.url')).get_connector()

    '''
        Get the history of installed version for a bank
    '''
    def history(self):
        pass

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
    def get_dict_sections(self, tool=None):
        if tool is None:
            raise Exception("A tool name is required to retrieve virtual info")

        ndbs = 'db.%s.nuc' % tool
        pdbs = 'db.%s.pro' % tool
        nsec = ndbs + '.sections'
        psec = pdbs + '.sections'
        dbs = {}

        if self.config.has_option(ndbs):
            dbs['nuc'] = {'dbs': []}
            for sec in split(self.config.get(ndbs), ','):
                dbs['nuc']['dbs'].append(sec)
        if self.config.has_option(pdbs):
            dbs['pro'] = {'dbs': []}
            for sec in split(self.config.get(pdbs)):
                dbs['pro']['dbs'].append(sec)
        if self.config.has_option(nsec):
            if 'nuc' in dbs:
                dbs['nuc']['secs'] = []
            else:
                dbs['nuc': {'dbs': []}]
            for sec in split(self.config.get(nsec)):
                dbs['nuc']['secs'].append(sec)
        if self.config.has_option(psec):
            if 'pro' in dbs:
                dbs['pro']['secs'] = []
            else:
                dbs['pro'] = {'secs': []}
            for sec in split(self.config.get(psec)):
                dbs['pro']['secs'].append(sec)

        if dbs.keys():
            dbs['inf'] = {'desc': self.config.get('db.fullname')
                          #,'vers': 1 or self.current_release.version() or ""}
                          }
            dbs['tool'] = tool
        return dbs

    '''
        Get the "supported" blast2/golden indexes for this bank
        Each bank can have some sub sections.

        :param tool: Name of the index to search
        :type tool: String
        :return: If info defined,
                 list of bank(s)/section(s) found
                 Otherwise empty list
    '''
    def get_list_sections(self, tool=None):
        if tool is None:
            raise Exception("A tool name is required to retrieve virtual info")

        ndbs = 'db.%s.nuc' % tool
        pdbs = 'db.%s.pro' % tool
        nsec = ndbs + '.sections'
        psec = pdbs + '.sections'
        dbs = []

        if self.config.has_option(ndbs):
            for sec in split(self.config.get(ndbs), ','):
                dbs.append(sec)
        if self.config.has_option(pdbs):
            for sec in split(self.config.get(pdbs), ','):
                dbs.append(sec)
        if self.config.has_option(nsec):
            for sec in split(self.config.get(nsec), ','):
                dbs.append(sec)
        if self.config.has_option(psec):
            for sec in split(self.config.get(psec), ','):
                dbs.append(sec)

        return dbs
