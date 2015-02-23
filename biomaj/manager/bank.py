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

    def __init__(self, name=None, connect=False, check_bank=False):

        # List of release loaded?
        self.has_releases = False
        # Do we have a future release ready?
        self.has_future = False

        if not name:
            raise Exception("A bank name is required!")
        self.name = name
        self.idbank = None
        if self.config is None:
            self.config = Config(name)
        if connect:
            self.db = Connector(self.config.get('db.url')).get_connector()
            if check_bank:
                self.__check_bank()

    def history(self):
        '''
            Get the release history of a specific bank

            :param name: Name of the bank
            :type name: String
            :return: A list with all the bank history
        '''
        # SQL
        # SELECT b.name, u.updateRelease,p.state, p.remove, p.creation, p.path FROM productionDirectory p
        # JOIN bank b ON b.idbank = p.ref_idbank
        # JOIN updateBank u ON u.idLastSession = p.session
        # WHERE b.name = 'calbicans5314' (AND p.creation > ?) [OPTIONAL]

        if not self.db:
            raise Exception("No db connection available. Build object with 'connect=True'.")

        session = self.db.sessionmaker()
        proddir = self.db.base.classes.productiondirectory
        bank = self.db.base.classes.bank
        updateBank = self.db.base.classes.updateBank
        releases = session.query(proddir.remove, proddir.creation, proddir.path, proddir.state, proddir.idproductiondirectory,\
                                 bank.name, updateBank.updaterelease).\
                                 join("bank").join("updatebank").\
                                 filter(bank.name==self.name).\
                                 order_by(proddir.idproductiondirectory)
        rel_list = []
        for rel in releases:
            rel_list.append({'id': rel.idproductiondirectory,
                             'name': rel.bank.name,
                             'release': rel.updatebank.updaterelease,
                             'removed': rel.remove,
                             'created': rel.created,
                             'path': rel.path,
                             'status': rel.status})
        session.close()
        return rel_list

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
                          ,'vers': self.available_releases[0].release or ""
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

    def full_info(self):
        """
            Get more information about a bank
        """
        if not self.has_releases:
            self.__load_releases()
        
        pass

    def __check_bank(self):
        bank = self.db.base.classes.bank
        session = self.db.sessionmaker()
        b = session.query(bank).filter(bank.name == self.name)
        if not session.query(b.exists()):
            raise Exception("Sorry bank %s not found" % self.name)
        self.idbank = b.first().idbank

    def __load_releases(self):
        """
            Search for all the available release for a particular bank
            It is based on the number of kept release (config: keep.old.version)
            Available release(s) are queried from the database
            :return: Int (0) if all ok
            :raise: Exception
        """

        if not self.db:
            raise Exception("No db connection available. Build object with 'connect=True'.")

        if self.has_releases:
            return 0

        limit = self.config.getint('keep.old.version')
        session = self.db.sessionmaker()
        prod = self.db.base.classes.productiondirectory
        updbk = self.db.base.classes.updatebank
        bank = self.db.base.classes.bank
        releases = session.query(prod).join(updbk).join(bank).\
                            filter(prod.ref_idbank == bank.idbank, bank.name == self.name).\
                            order_by(prod.creation.desc())

        self.current_releases = []
        self.old_releases = []
        rows = 0

        for release in releases:
            rel = BankRelease()
            rel.name = self.name
            rel.release = release.updatebank.updaterelease
            rel.creation = release.creation
            rel.download = release.updatebank.sizedownload
            rel.started = release.updatebank.starttime
            rel.ended = release.updatebank.endtime
            rel.path = release.path
            rel.size = release.size
            rel.status = release.state
            rel.removed = release.removed
            rel.session = release.session
            if rows < limit:
                if rows == 0:
                    rel.kind = 'current'
                else:
                    rel.kind = 'previous'
                rel.online = True
                self.available_releases.append(rel)
            else:
                rel.kind = 'old'
                rel.online = False
                self.old_releases.append(rel)
            rows += 1
        # Keep trace we have loaded releases
        self.has_releases = True
        return 0

    def __load_future_release(self):

        if not self.db:
            raise Exception("No db connection available. Build object with 'connect=True'.")

        if self.has_future:
            return 0

        configuration = self.db.base.classes.configuration
        updbk = self.db.base.classes.updatebank
        session = self.db.sessionmaker()
        releases = session.query(configuration).join(updbk).filter(configuration.ref_idbank == self.idbank).\
                    filter(updbk.isupdated == 1, updbk.updaterelease != None,
                           updbk.productiondirectorypath != 'null').\
                           order_by(updbk.starttime.desc)

        for release in releases:
            if release.updatebank.productiondirectorydeployed:
                break
            rel = BankRelease()
            rel.name = self.name
            rel.release = release.updatebank.updaterelease
            rel.start = release.updatebank.starttime
            rel.ended = release.updatebank.endtime
            rel.creation = release.updatebank.updated
            rel.path = release.updatebank.productiondirectorypath
            rel.size = release.updatebank.sizerelease
            rel.downloaded = release.updatebank.sizedownload
            self.future_release = rel

        self.has_future = True
        return 0


class BankRelease:

    def __init__(self, creation=None, path=None, session=None, size=None, kind=None,
                 download=None, release=None, started=None, ended=None, status=None,
                 removed=None, name=None, online=False):
        self.creation = creation
        self.removed = removed
        self.path = path
        self.session = session
        self.size = size
        self.kind = kind
        self.online = online
        self.download = download
        self.release = release
        self.started = started
        self.ended = ended
        self.release = 'NA'
        self.status = status
        self.name = name

    def info(self):
        """
            Prints information about a bank release
        """
        print("Bank         : %s" % self.name)
        print("Type         : %s" % self.kind)
        print("Online       : %s" % str(self.online))
        print("Release      : %s" % self.release)
        print("Status       : %s" % self.status)
        print("Creation     : %s" % self.creation)
        print("Removed      : %s" % self.removed)
        print("Last session : %s" % self.session)
        print("Path         : %s" % self.path)
        print("Size         : %s" % str(self.size))
        print("Downloaded   : %s" % self.download)
        print("Started      : %s" % self.started)
        print("Ended        : %s" % self.ended)
        print("Last session : %s" % self.session)

