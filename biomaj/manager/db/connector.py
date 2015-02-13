'''
Created on Feb 10, 2015

@author: tuco
'''

from biomaj.mongo_connector import MongoConnector
from sqlalchemy import create_engine
from string import split


class Connector:

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

        Connector.url = url
        Connector.db = db
        Connector.driver = driver

    def get_connector(self):
        if Connector.url is None or Connector.db is None:
            raise Exception("Can't create connector, params not set!")
        if Connector.driver == 'mongo':
            return MongoConnector(Connector.url, Connector.db)
        else:
            return SQLConnector()


class SQLConnector(Connector):

    '''
    Class to connect to a SQL database (PostgreSQL, MySQL, Oracle...)
    using sqlalchemy ORM
    '''

    def __init__(self):
        # 'mysql://scott:tiger@localhost/test'
        print "PgConnector is set!"
        self.engine = create_engine(Connector.url)
        print self.__module__

    def print_infos(self):
        print self.__module__

    def get_bank_list(self):
        connection = self.engine.connect()
        banks = connection.execute("select amorceid,amorcename from amorces limit 10")
        for bank in banks:
            print "[%s] %s" % (bank['amorceid'], bank['amorcename'])
        return

    def get_history(self, name):
        pass