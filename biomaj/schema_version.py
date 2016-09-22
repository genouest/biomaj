import pkg_resources
from biomaj.mongo_connector import MongoConnector
from biomaj.config import BiomajConfig


class SchemaVersion(object):

    """
    BioMAJ database schema version. This package can be used to make some schema modification if needed during
    incremental software version.
    """

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
                print("* SchemaVersion: Can't find config file")
                return None
        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                           BiomajConfig.global_config.get('GENERAL', 'db.name'))

        schema = MongoConnector.db_schema
        banks = MongoConnector.banks

        schema_version = schema.find_one({'id': 1})
        installed_version = pkg_resources.get_distribution("biomaj").version
        if schema_version is None:
            schema_version = {'id': 1, 'version': '3.0.0'}
            schema.insert(schema_version)

        moderate = int(schema_version['version'].split('.')[1])
        minor = int(schema_version['version'].split('.')[2])

        if moderate == 0 and minor <= 17:
            print("Migrate from release: %s" % schema_version['version'])
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
        schema.update_one({'id': 1}, {'$set': {'version': installed_version}})
