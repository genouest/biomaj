from biomaj.schema_version import SchemaVersion
import logging

logging.warn('Migrate BioMAJ database...')
logging.warn('Needs global.properties in local directory or env variable BIOMAJ_CONF')
SchemaVersion.migrate_pendings()
logging.warn('Migration done')
