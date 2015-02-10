'''
Created on Feb 6, 2015

@author: tuco
'''
from ConfigParser import ConfigParser
# import MySQLdb
from biomaj.manager.config import Config
from biomaj.manager.connector import Connector


class Bank():

    config = None
    db = None

    def __init__(self, name=None, connect=True):

        if not name:
            raise Exception("A bank name is required!")
        if self.config is None:
            self.config = Config(name)
        if connect:
            self.db = Connector(self.get('db.url'))