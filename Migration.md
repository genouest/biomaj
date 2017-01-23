---
title: Migration
layout: default
---

# From biomaj 1


Use [https://github.com/genouest/biomaj-migrate](https://github.com/genouest/biomaj-migrate) to migrate existing data from MySQL to MongoDB

Some properties have been changed or deprecated.

See process env variables for deprecated variables.

Global and bank properties:

* bank property files and global.properties must start with [GENERAL] section name.
* regexp have single backslash instead of double backslash
* regexp do not need backslash in front of slashes: aaa\/w+ => aaa/w+


# From bioMAJ 3.x

## Database schema

While upgrade of biomaj usually consists of updating packages via pip (or other means), a database schema modification can occurs.
While biomaj tries to update it automatically at install (if it founds the global.properties), it may fail (fails to connect to database, global.properties not found, ...).

To manually upgrade biomaj schema you need to execute the following commands in a python shell or script:


        from biomaj.schema_version import SchemaVersion
        SchemaVersion.migrate_pendings()


If not sure, there is no danger in running it multiple times.... biomaj will check the schema version.

## Upgrading to micro service architecture

Biomaj > 3.1 gives the possibility to deploy the software in a micro service architecture, with multiple servers specialized and scalable.
This is not mandatory (though you will not benefit of additional options) !
You can still install and use biomaj as a monolithic software, calling biomaj-cli as usual. To do so however, different packages have been created and updating biomaj package is not enough, you also need to install biomaj-cli and biomaj-daemon.
