'''
Created on Feb 6, 2015

@author: tuco
'''
from ConfigParser import ConfigParser
# import MySQLdb
from biomaj.manager.config import Config
from biomaj.manager.db.connector import Connector
from string import split
import json
import os

class Bank:

    config = None
    db = None

    def __init__(self, name=None, connect=False):

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
        if self.config is None:
            self.config = Config(name=name)
        if connect:
            self.db = Connector(self.config.get('db.url')).get_connector()
            self.__check_bank()

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
            raise Exception("Can't get format(s) for '%s', directory not found" % path)
        if flat:
            return ','.join(os.listdir(path))
        return os.listdir(path)

    def history(self, to_json=False):
        '''
            Get the release history of a specific bank

            :param to_json: Converts output to json
            :type name: Boolean (Default False)
            :return: A list with all the bank history
        '''
        # SQL
        # SELECT b.name, u.updateRelease,p.state, p.remove, p.creation, p.path FROM productionDirectory p
        # JOIN updateBank u ON u.idLastSession = p.session
        # WHERE b.name = 'calbicans5314' (AND p.creation > ?) [OPTIONAL]

        if not self.db:
            raise Exception("No db connection available. Build object with 'connect=True'.")

        session = self.db.sessionmaker()
        proddir = self.db.base.classes.productionDirectory
        bank = self.db.base.classes.bank
        updateBank = self.db.base.classes.updateBank
        releases = session.query(proddir, updateBank).\
                                join(updateBank, updateBank.idLastSession == proddir.session).\
                                filter(proddir.ref_idbank==self.idbank).\
                                order_by('productionDirectory.idproductionDirectory DESC')
        rel_list = []
        for p, u in releases:
            rel_list.append({'id': "%d" % p.idproductionDirectory,
                             'name': self.name,
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

    def history_tomongo(self):
        """
            Get the releases history of a bank from the database and build a Mongo like document in json
            :return: Jsonified list
        """
        session = self.db.sessionmaker()
        proddir = self.db.base.classes.productionDirectory
        updateBank = self.db.base.classes.updateBank
        releases = session.query(proddir, updateBank).join(updateBank, proddir.session == updateBank.idLastSession).\
                            filter(proddir.ref_idbank==self.idbank).\
                            order_by('productionDirectory.idproductionDirectory DESC')
        rel_list = []
        for p, u in releases:
            rel_list.append({'_id': '@'.join(['bank', self.name, u.updateRelease]),
                             'type': 'bank',
                             'name': self.name,
                             'version': u.updateRelease or None,
                             'publication_date': p.creation.strftime("%Y-%m-%d %X") if p.creation else None,
                             'removal_date': p.remove.strftime("%Y-%m-%d %X") if p.remove else None,
                             'bank_type': split(self.config.get('db.type'), ','),  # Can be taken from db table remoteInfo.dbType
                             'bank_format': split(self.config.get('db.formats'), ','),
                             'programs': self.__get_formats_for_release(p.path)}
                            )
        print "History_to_mongo: %d entries" % len(rel_list)
        return json.dumps(rel_list)

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
        releases = self.available_releases
        releases.extend(self.removed_releases)
        for release in releases:
            release.info()
        return

    def __check_bank(self):
        """
            Checks a bank exists in the database
            :param name: Name of the bank to check [Default self.name]
            :param name: String
            :return:
            :throws: Exception if bank does not exists
        """
        self.__is_connected()
        if not self.name:
            raise Exception("Can't check bank, name not set")
        bank = self.db.base.classes.bank
        session = self.db.sessionmaker()
        b = session.query(bank).filter(bank.name == self.name)
        if not session.query(b.exists()):
            raise Exception("Sorry bank %s not found" % self.name)
        self.idbank = b.first().idbank

    def __get_formats_for_release(self, path):
        """
            Get all the formats supporeted for a bank (path).
            :param path: Path of the release to search in
            :type path: String (path)
            :return: List of formats
        """
        path = '/tmp/banks'
        if not path:
            raise Exception("A path is required")
        if not os.path.exists(path):
            raise Exception("Path %s does not exist" % path)
        formats = []

        for dir, dirs, filenames in os.walk(path):
            if dir == path or not len(dirs):
                continue
            if dir == 'flat' or dir == 'uncompressed':
                continue
            for d in dirs:
                formats.append('@'.join(['prog', os.path.basename(dir), d or '-', '?']))
        return formats

    def __is_connected(self):
        """
            Check the bank object has a connection to the database set.
            :return: raise Exception if no connection set
        """
        if self.db:
            return True
        else:
            raise Exception("No db connection available. Build object with 'connect=True' to access database.")

    def __load_releases(self):
        """
            Search for all the available release for a particular bank
            It is based on the number of kept release (config: keep.old.version)
            Available release(s) are queried from the database
            :return: Int (0) if all ok
            :raise: Exception
        """

        self.__is_connected()
        if self.has_releases:
            return 0

        limit = self.config.getint('keep.old.version')
        session = self.db.sessionmaker()
        prod = self.db.base.classes.productionDirectory
        updbk = self.db.base.classes.updateBank
        bank = self.db.base.classes.bank
        releases = session.query(prod, updbk).join(updbk, updbk.idLastSession == prod.session).\
                            join(bank, bank.idbank == prod.ref_idbank).\
                            filter(bank.name == self.name).\
                            order_by(prod.creation.desc())

        self.old_releases = []
        rows = 0

        for p, u in releases:
            rel = BankRelease()
            rel.name = self.name
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
            if rows <= limit:
                if rows == 0:
                    rel.kind = 'current'
                else:
                    rel.kind = 'previous'
                rel.online = True
                self.available_releases.append(rel)
            else:
                rel.kind = 'removed'
                rel.online = False
                self.removed_releases.append(rel)
            rows += 1
        # Keep trace we have loaded releases
        self.has_releases = True if len(self.available_releases) else False
        return 0

    def __load_future_release(self):
        '''
            Load the release tagged has 'future' from the database. Those release are just release that have
            been build and are not published yet. We stopped the workflow before the 'deployement' stage.
            :return: Int
                     Raise Exception on error
        '''
        self.__is_connected()
        if self.future_release is not None:
            return 0

        configuration = self.db.base.classes.configuration
        updbk = self.db.base.classes.updatebank
        session = self.db.sessionmaker()
        releases = session.query(configuration, updbk).\
                            join(updbk, updbk.ref_idconfiguration == configuration.idconfiguration).\
                            filter(configuration.ref_idbank == self.idbank).\
                            filter(updbk.isupdated == 1, updbk.updaterelease != None,
                                   updbk.productiondirectorypath != 'null').\
                                   order_by(updbk.starttime.desc)

        for c, u in releases:
            if u.productionDirectoryDeployed:
                break
            rel = BankRelease()
            rel.name = self.name
            rel.release = u.updateRelease
            rel.start = u.startTime
            rel.ended = u.endTime
            rel.creation = u.isUpdated
            rel.path = u.productionDirectoryPath
            rel.size = u.sizeRelease
            rel.downloaded = u.sizeDownload
            self.future_release = rel
            break

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
        print("----------------------")
        print("Bank         : %s" % self.name)
        print("Kind         : %s" % self.kind)
        print("Available    : %s" % str(self.online))
        print("Status       : %s" % self.status)
        print("Release      : %s" % self.release)
        print("Creation     : %s" % self.creation)
        print("Removed      : %s" % self.removed)
        print("Last session : %s" % self.session)
        print("Path         : %s" % self.path)
        print("Size         : %s" % str(self.size))
        print("Downloaded   : %s" % self.download)
        print("Started      : %s" % self.started)
        print("Ended        : %s" % self.ended)
        print("Last session : %s" % self.session)
        print("----------------------")
