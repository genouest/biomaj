

from biomaj.manager.bankrelease import BankRelease
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from sqlalchemy.ext.automap import automap_base
from string import split
import json

class SQLConnector:

    '''
    Class to connect to a SQL database (PostgreSQL, MySQL, Oracle...)
    using sqlalchemy ORM
    '''

    url = None
    db = None
    driver = None

    def __init__(self, url):
        # 'mysql://scott:tiger@localhost/test'
        self.engine = create_engine(url)
        self.db = split(url, '/')[-1]
        self.meta = MetaData()
        self.base = automap_base()
        self.base.prepare(self.engine, reflect=True)
        self.meta.reflect(bind=self.engine)
        self.sessionmaker = sessionmaker(bind=self.engine)

    def _is_connected(self):
        return True if self.sessionmaker else False

    def _history(self, bank=None, to_json=False):
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
        if not bank:
            raise Exception("Bank instance is required")

        session = self.sessionmaker()
        proddir = self.base.classes.productionDirectory
        updateBank = self.base.classes.updateBank
        releases = session.query(proddir, updateBank).\
                                join(updateBank, updateBank.idLastSession == proddir.session).\
                                filter(proddir.ref_idbank == bank.idbank).\
                                order_by('productionDirectory.idproductionDirectory DESC')
        rel_list = []
        for p, u in releases:
            rel_list.append({'id': "%d" % p.idproductionDirectory,
                             'name': bank.name,
                             'release': u.updateRelease,
                             'removed': p.remove.strftime("%Y-%m-%d %X") if p.remove else None, # p.remove is a datetime.datetime
                             'created': p.creation.strftime("%x %X"),
                             'path': p.path,
                             'status': p.state})
        session.commit()
        session.close()
        print "History: %d entries" % len(rel_list)
        if to_json:
            return json.dumps(rel_list)
        return rel_list

    def _mongo_history(self, bank=None):
        """
            Get the releases history of a bank from the database and build a Mongo like document in json
            :param name: Name of the bank
            :type name: String
            :param idbank: Bank id (primary key)
            :tpye idbank: Integer
            :return: Jsonified history + extra info to be included into bioweb (Institut Pasteur only)
        """
        if not bank:
            raise Exception("Bank instance is required")

        session = self.sessionmaker()
        proddir = self.base.classes.productionDirectory
        updateBank = self.base.classes.updateBank
        releases = session.query(proddir, updateBank).join(updateBank, proddir.session == updateBank.idLastSession).\
                            filter(proddir.ref_idbank==bank.idbank).\
                            order_by('productionDirectory.idproductionDirectory DESC')
        rel_list = []
        for p, u in releases:
            rel_list.append({'_id': '@'.join(['bank', bank.name, u.updateRelease]),
                             'type': 'bank',
                             'name': bank.name,
                             'version': u.updateRelease or None,
                             'publication_date': p.creation.strftime("%Y-%m-%d %X") if p.creation else None,
                             'removal_date': p.remove.strftime("%Y-%m-%d %X") if p.remove else None,
                             'bank_type': split(bank.config.get('db.type'), ','),  # Can be taken from db table remoteInfo.dbType
                             'bank_format': split(bank.config.get('db.formats'), ','),
                             'programs': bank._get_formats_for_release(p.path) }
                            )

        print "History_to_mongo: %d entries" % len(rel_list)
        return json.dumps(rel_list)

    def get_bank_list(self):
        '''
            Small function to test postgresql connection and sqlalchemy
        '''
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

    def get_banks(self, visibility ='public'):
        """
            Just prints the list of banks handled by biomaj in its database
            :param visibility: Visibility of the bank (public[Default]|private)
            :type visibility: String
            :return: Prints to STDOUT
        """

        if visibility != 'public' and visibility != 'private':
            raise Exception("Visibility must be public|private")
        banks = self.base.classes.bank
        session = self.sessionmaker()
        private = False if visibility == 'private' else True
        banks = session.query(banks).filter(banks.visibility == private).all()
        for bank in banks:
            print "[%d] %s is %s" % (bank.idbank, bank.name, 'public' if bank.visibility else 'private')
        return 0

    def _check_bank(self, name=None):
        """
            Checks a bank exists in the database
            :param name: Name of the bank to check [Default self.name]
            :param name: String
            :return:
            :throws: Exception if bank does not exists
        """
        self._is_connected()
        if name is None:
            raise Exception("Can't check bank, name not set")
        bank = self.base.classes.bank
        session = self.sessionmaker()
        b = session.query(bank).filter(bank.name == name)
        if not session.query(b.exists()):
            raise Exception("Bank %s does not exist" % name)
        return b.first().idbank

    def _get_releases(self, bank):
        """
            Search for all the available release for a particular bank
            It is based on the number of kept release (config: keep.old.version)
            Available release(s) are queried from the database
            :param: Bank instance
            :type: biomaj.BankString
            :return: Int (0) if all ok
            :raise: Exception
        """

        self._is_connected()

        session = self.sessionmaker()
        prod = self.base.classes.productionDirectory
        updbk = self.base.classes.updateBank
        banktb = self.base.classes.bank
        releases = session.query(prod, updbk).join(updbk, updbk.idLastSession == prod.session).\
                            join(banktb, banktb.idbank == prod.ref_idbank).\
                            filter(banktb.name == bank.name).\
                            order_by(prod.creation.desc())

        rows = 0

        for p, u in releases:
            rel = BankRelease()
            rel.name = bank.name
            rel.release = u.updateRelease
            rel.creation = p.creation
            rel.download = u.sizeDownload
            rel.started = u.startTime
            rel.ended = u.endTime
            rel.path = p.path
            rel.size = p.size
            rel.status = p.state
            rel.removed = p.remove
            rel.session = p.session
            if rows <= bank.config.get('keep.old.version'):
                if rows == 0:
                    rel.kind = 'current'
                else:
                    rel.kind = 'previous'
                rel.online = True
                bank.available_releases.append(rel)
            else:
                rel.kind = 'removed'
                rel.online = False
                bank.removed_releases.append(rel)
            rows += 1
        # Keep trace we have loaded releases
        bank.has_releases = True if len(bank.available_releases) else False
        return 0

    def _get_future_release(self, bank):
        '''
            Load the release tagged has 'future' from the database. Those release are just release that have
            been build and are not published yet. We stopped the workflow before the 'deployement' stage.
            :return: Int
                     Raise Exception on error
        '''
        self._is_connected()
        if bank.future_release is not None:
            return 0

        configuration = self.base.classes.configuration
        updbk = self.classes.updatebank
        session = self.sessionmaker()
        releases = session.query(configuration, updbk).\
                            join(updbk, updbk.ref_idconfiguration == configuration.idconfiguration).\
                            filter(configuration.ref_idbank == bank.idbank).\
                            filter(updbk.isupdated == 1, updbk.updaterelease != None,
                                   updbk.productiondirectorypath != 'null').\
                                   order_by(updbk.starttime.desc)

        for c, u in releases:
            if u.productionDirectoryDeployed:
                break
            rel = BankRelease()
            rel.name = bank.name
            rel.release = u.updateRelease
            rel.start = u.startTime
            rel.ended = u.endTime
            rel.creation = u.isUpdated
            rel.path = u.productionDirectoryPath
            rel.size = u.sizeRelease
            rel.downloaded = u.sizeDownload
            bank.future_release = rel
            break

        return 0