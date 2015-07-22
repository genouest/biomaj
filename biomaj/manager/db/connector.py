'''
Created on Feb 10, 2015

@author: tuco
'''

from biomaj.manager.db.nosqlconnector import NoSQLConnector
from biomaj.manager.db.sqlconnector import SQLConnector

from string import split
import json

class BaseConnector:

    url = None
    db = None
    driver = None

    def __init__(self, url=None, db='biomaj_log'):
        # If connector type not set, try to get it from the global.properties
        if url is None:
            raise Exception("No connection url set!")
        if db is None:
            raise Exception("No connection db set!")
        driver = split(url, ':')[0]
        if not driver:
            raise Exception("Can't determine database driver")

        BaseConnector.url = url
        BaseConnector.db = db
        BaseConnector.driver = driver

    def get_connector(self):
        if BaseConnector.url is None or BaseConnector.db is None:
            raise Exception("Can't create connector, params not set!")
        if BaseConnector.driver == 'mongodb':
            return NoSQLConnector(BaseConnector.url, BaseConnector.db)
        else:
            return SQLConnector(BaseConnector.url)

