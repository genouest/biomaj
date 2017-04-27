from __future__ import print_function
import pkg_resources
import string
import random
import os
import sys
from biomaj.bank import Bank
from biomaj.mongo_connector import MongoConnector
from biomaj_core.config import BiomajConfig
from biomaj_core.utils import Utils

import logging


class SchemaVersion(object):

    """
    BioMAJ database schema version. This package can be used to make some schema modification if needed during
    incremental software version.
    """

    VERSION = None

    @staticmethod
    def migrate_pendings():
        """
        Migrate database

        3.0.18: Check the actual BioMAJ version and if older than 3.0.17, do the 'pending' key migration
        """
        if BiomajConfig.global_config is None:
            try:
                BiomajConfig.load_config()
            except Exception as err:
                print("* SchemaVersion: Can't find config file: " + str(err))
                return None
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        schema = MongoConnector.db_schema
        banks = MongoConnector.banks
        users = MongoConnector.users
        schema_version = SchemaVersion.get_dbschema_version(schema)
        moderate = int(schema_version.split('.')[1])
        minor = int(schema_version.split('.')[2])

        if moderate == 0 and minor <= 17:
            print("Migrate from release: %s" % schema_version)
            # Update pending releases
            bank_list = banks.find()
            updated = 0
            for bank in bank_list:
                if 'pending' in bank:
                    # Check we have an old pending type
                    if type(bank['pending']) == dict:
                        updated += 1
                        pendings = []
                        for release in sorted(bank['pending'], key=lambda r: bank['pending'][r]):
                            pendings.append({'release': str(release), 'id': bank['pending'][str(release)]})
                        if len(pendings) > 0:
                            banks.update({'name': bank['name']},
                                         {'$set': {'pending': pendings}})
                    else:
                        # We remove old type for 'pending'
                        banks.update({'name': bank['name']},
                                     {'$unset': {'pending': ""}})

            print("Migration: %d bank(s) updated" % updated)
        if moderate < 1:
            updated = 0
            user_list = users.find()
            for user in user_list:
                if 'apikey' not in user:
                    updated += 1
                    api_key = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
                    users.update({'_id': user['_id']}, {'$set': {'apikey': api_key}})
            print("Migration: %d user(s) updated" % updated)
            # production size
            bank_list = banks.find()
            updated = 0
            for bank in bank_list:
                for prod in bank['production']:
                    '''
                    { "_id" : ObjectId("54edb10856e8bb11340b5f51"), "production" : [
                        { "freeze" : false, "remoterelease" : "2003-11-26", "session" : 1427809848.560108,
                        "data_dir" : "/db", "formats" : [ ], "release" : "2003-11-26",
                        "dir_version" : "ncbi/blast/alu",
                        "prod_dir" : "alu-2003-11-26", "types" : [ ], "size" : 319432 } ] }
                    '''
                    if 'size' not in prod or prod['size'] == 0:
                        logging.info('Calculate size for bank %s' % (bank['name']))
                        if 'data_dir' not in prod or not prod['data_dir'] or 'prod_dir' not in prod or not prod['prod_dir'] or 'dir_version' not in prod or not prod['dir_version']:
                            logging.warn('no production directory information for %s, skipping...' % (bank['name']))
                            continue
                        prod_dir = os.path.join(prod['data_dir'], prod['dir_version'], prod['prod_dir'])
                        if not os.path.exists(prod_dir):
                            logging.warn('production directory %s does not exists for %s, skipping...' % (prod_dir, bank['name']))
                            continue
                        dir_size = Utils.get_folder_size(prod_dir)
                        banks.update({'name': bank['name'], 'production.release': prod['release']}, {'$set': {'production.$.size': dir_size}})
                        updated += 1
            print("Migration: %d bank production info updated" % updated)

    @staticmethod
    def add_property(bank=None, prop=None, value=None, cfg=None):
        """
        Update properties field for banks.

        :param bank: Bank name to update, default all
        :type bank: str
        :param prop: New property to add
        :type prop: str
        :param value: Property value, if cfg set, value taken
                      from bank configuration cfg key
        :type value: str
        :param cfg: Bank configuration key value is taken from
        :type cfg: str

        :raise Exception: If not configuration file found
        :returns: True/False
        :rtype: bool
        """
        if BiomajConfig.global_config is None:
            try:
                BiomajConfig.load_config()
            except Exception as err:
                print("* SchemaVersion: Can't find config file: " + str(err))
                return False
        if prop is None:
            print("Property key is required", file=sys.stderr)
            return False

        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        schema = MongoConnector.db_schema
        banks = MongoConnector.banks
        schema_version = SchemaVersion.get_dbschema_version(schema)
        moderate = int(schema_version.split('.')[1])
        minor = int(schema_version.split('.')[2])

        if moderate <= 1 and minor <= 0:
            bank_list = []
            if bank is None:
                bank_list = banks.find()
            else:
                bank_list = [banks.find_one({'name': bank})]
            updated = 0
            for bank in bank_list:
                if 'properties' in bank:
                    b = Bank(bank['name'], no_log=True)
                    new_prop = 'properties.' + prop
                    new_value = value
                    if new_value is None:
                        if cfg is not None:
                            new_value = b.config.get(cfg)
                        else:
                            print("[%s] With value set to None, you must set cfg to get "
                                  "corresponding value" % str(bank['name']), file=sys.stderr)
                            continue
                    banks.update({'name': bank['name']},
                                 {'$set': {new_prop: new_value}})
                    updated += 1
                else:
                    logging.warn("Bank %s does not have 'properties' field!" % str(bank['name']))

            print("Add property: %d bank(s) updated" % updated)

    @staticmethod
    def get_dbschema_version(schema):
        """
        Get the version of the actual schema version stored in database

        :param schema: Mongo schema info
        :type schema: MongoDB collection
        :returns: moderate, minor
        :rtype: int, int

        """
        schema_version = schema.find_one({'id': 1})
        if schema_version is None:
            schema_version = {'id': 1, 'version': '3.0.0'}
            schema.insert(schema_version)
        return schema_version['version']

    @staticmethod
    def set_version(version=None):
        """
        Set BioMAJ current installed version in db_schema collection if version is None

        :param version: db_schema collection version to set
        :type version: str
        """
        installed_version = version
        if installed_version is None:
            installed_version = pkg_resources.get_distribution("biomaj").version
        if BiomajConfig.global_config is None:
            try:
                BiomajConfig.load_config()
            except Exception as err:
                print("* SchemaVersion: Can't find config file: " + str(err))
                return None
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))
        schema = MongoConnector.db_schema
        schema.update_one({'id': 1}, {'$set': {'version': installed_version}})
        print("Schema version set to %s" % str(installed_version))
