'''
Created on Feb 10, 2015

@author: tuco
'''

from biomaj.manager.bank import Bank
from biomaj.mongo_connector import MongoConnector
from biomaj.manager.connector.pg_connector import PgConnector
from string import split

class Connector():

    def __init__(self, type=None):
        # If connector type not set, try to get it from the global.properties
        if type is None:
            raise Exception("No connection type set!")
        dbtype = split(type, ':')[0]
        if dbtype == 'pg':
            return PgConnector(type)
        else:
            return MongoConnector()
        return self