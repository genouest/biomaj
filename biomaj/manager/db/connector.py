'''
Created on Feb 10, 2015

@author: tuco
'''

from biomaj.mongo_connector import MongoConnector
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from sqlalchemy.ext.automap import automap_base
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
        self.engine = create_engine(Connector.url)
        Connector.db = split(Connector.url, '/')[-1]
        self.meta = MetaData()
        self.base = automap_base()
        self.base.prepare(self.engine, reflect=True)
        self.meta.reflect(bind=self.engine)
        self.sessionmaker = sessionmaker(bind=self.engine)

    '''
        Small function to test postgresql connection and sqlalchemy
    '''
    def get_bank_list(self):
        print "[RAW SQL] Tesing ... "
        connection = self.engine.connect()
        banks = connection.execute("select idbank, name from bank where idbank < 5")
        for bank in banks:
            print "[%s] %s" % (bank['idbank'], bank['name'])
        print "[RAW SQL] OK"

        print "[SESSION] Testing ..."
        session = self.sessionmaker()
        bank = self.base.classes.bank
        banks = session.query(bank).filter(bank.idbank < 5)
        for bank in banks:
            print "[session][%s] %s" % (bank.idbank, bank.name)
        session.commit()
        session.close()
        print "[SESSION] OK"

        print "[SESSION+JOIN] Testing ..."
        session = self.sessionmaker()
        updbk = self.base.classes.updateBank
        bank = self.base.classes.bank
        proddir = self.base.classes.productionDirectory
        sample = session.query(proddir, bank, updbk).\
                        join(updbk, updbk.idLastSession == proddir.session).\
                        join(bank, bank.idbank == proddir.ref_idbank).\
                        filter(bank.name == 'genbank_release').\
                        filter(proddir.state == 'available')
        for s, b, u in sample:  
            print "[id:%d] %s [r%s]" \
                % (s.idproductionDirectory, b.name, u.updateRelease)
        session.commit()
        session.close()
        print "[SESSION+JOIN] OK"

        print "[EXISTS] Testing ..."
        session = self.sessionmaker()
        bank = self.base.classes.bank
        fake_bank = 'fake_foobank'
        smt = exists().where(bank.name == fake_bank)
        if session.query(bank).filter(smt):
            print "Bank %s does not exists" % fake_bank
        else:
            print "It works"
        print "[EXISTS] OK"
        session.commit()
        session.close()
        return

    def get_banks(self, type='public'):
        """
            Just prints the list of banks handled by biomaj in its database
            :param type: Type of the bank (public[Default]|private)
            :type type: String
            :return: Prints to STDOUT
        """

        if type != 'public' and type != 'private':
            raise Exception("Type must be public|private")
        banks = self.base.classes.bank
        session = self.sessionmaker()
        private = False if type == 'private' else True
        banks = session.query(banks).filter(banks.visibility==private).all()
        for bank in banks:
            print "[%d] %s is %s" % (bank.idbank, bank.name, 'public' if bank.visibility else 'private')
        return 0

    """
    def get_table(self, name=None):
        if name is None:
            raise Exception("Table name required")
        if name in SQLConnector.meta.tables:
            return SQLConnector.meta.tables[name]
        else:
            raise "Table %s does not exist!" % (name)
    """