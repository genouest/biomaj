BioMAJ3
=====

This project is a complete rewrite of BioMAJ and the documentation is available here : http://biomaj.genouest.org.

BioMAJ (BIOlogie Mise A Jour) is a workflow engine dedicated to data
synchronization and processing. The Software automates the update cycle and the
supervision of the locally mirrored databank repository.

Common usages are to download remote databanks (Genbank for example) and apply
some transformations (blast indexing, emboss indexing, etc.). Any script can be
applied on downloaded data. When all treatments are successfully applied, bank
is put in "production" on a dedicated release directory.
With cron tasks, update tasks can be executed at regular interval, data are
downloaded again only if a change is detected.

More documentation is available in wiki page.

BioMAJ is python 2 and 3 compatible until release 3.1.17.
After 3.1.17, only python 3 is supported.

Getting started
===============

Edit global.properties file to match your settings. Minimal conf are database connection and directories.

    biomaj-cli.py -h

    biomaj-cli.py --config global.properties --status

    biomaj-cli.py --config global.properties  --bank alu --update

Migration
=========

To migrate from previous BioMAJ 1.x, a script is available at:
https://github.com/genouest/biomaj-migrate. Script will import old database to
the new database, and update configuration files to the modified format. Data directory is the same.

Migration for 3.0 to 3.1:

Biomaj 3.1 provides an optional micro service architecture, allowing to separate and distributute/scale biomaj components on one or many hosts. This implementation is optional but recommended for server installations. Monolithic installation can be kept for local computer installation.
To upgrade an existing 3.0 installation, as biomaj code has been split into multiple components, it is necessary to install/update biomaj python package but also biomaj-cli and biomaj-daemon packages. Then database must be upgraded manually (see Upgrading in documentation).

To execute database migration:

    python biomaj_migrate_database.py

Application Features
====================

* Synchronisation:
  * Multiple remote protocols (ftp, ftps, http, local copy, etc.)
  * Data transfers integrity check
  * Release versioning using a incremental approach
  * Multi threading
  * Data extraction (gzip, tar, bzip)
  * Data tree directory normalisation
  * Plugins support for custom downloads

* Pre &Post processing :
  * Advanced workflow description (D.A.G)
  * Post-process indexation for various bioinformatics software (blast, srs, fastacmd, readseq, etc.)
  * Easy integration of personal scripts for bank post-processing automation

* Supervision:
  * Optional Administration web interface (biomaj-watcher)
  * CLI management
  * Mail alerts for the update cycle supervision
  * Prometheus and Influxdb optional integration
  * Optional consul supervision of processes


* Scalability:
  * Monolithic (local install) or microservice architecture (remote access to a BioMAJ server)
  * Microservice installation allows per process scalability and supervision (number of process in charge of download, execution, etc.)

* Remote access:
  * Optional FTP server providing authenticated or anonymous data access
  * HTTP access to bank files (/db endpoint, microservice setup only)

Dependencies
============

Packages:

* Debian: libcurl-dev, gcc
* CentOs: libcurl-devel, openldap-devel, gcc

 Linux tools: tar, unzip, gunzip, bunzip

Database:
 * mongodb (local or remote)

Indexing (optional):
 * elasticsearch (global property, use_elastic=1)

ElasticSearch indexing adds advanced search features to biomaj to find bank having files with specific format or type.
Configuration of ElasticSearch is not in the scope of BioMAJ documentation.
For a basic installation, one instance of ElasticSearch is enough (low volume of data), in such a case, the ElasticSearch configuration file should be modified accordingly:

    node.name: "biomaj" (or any other name)
    index.number_of_shards: 1
    index.number_of_replicas: 0

Installation
============

From source:

After dependencies installation, go in BioMAJ source directory:

    python setup.py install

From packages:

    pip install biomaj biomaj-cli biomaj-daemon

You should consider using a Python virtual environment (virtualenv) to install BioMAJ.

In tools/examples, copy the global.properties and update it to match your local
installation.

The tools/process contains example process files (python and shell).

Docker
======

You can use BioMAJ with Docker (osallou/biomaj-docker)

    docker pull osallou/biomaj-docker
    docker pull mongo
    docker run --name biomaj-mongodb -d mongo
    # Wait ~10 seconds for mongo to initialize
    # Create a local directory where databases will be permanently stored
    # *local_path*
    docker run --rm -v local_path:/var/lib/biomaj --link biomaj-mongodb:biomaj-mongodb osallou/biomaj-docker --help

Copy your bank properties in directory *local_path*/conf and post-processes (if any) in *local_path*/process

You can override global.properties in /etc/biomaj/global.properties (-v xx/global.properties:/etc/biomaj/global.properties)

No default bank property file or process are available in the container.

Examples are available at https://github.com/genouest/biomaj-data


Import bank templates
=====================

Once biomaj is installed, it is possible to import some bank examples with the biomaj client


    # List available templates
    biomaj-cli ... --data-list
    # Import a bank template
    biomaj-cli ... --data-import --bank alu
    # then edit bank template in config directory if needed and launch bank update
    biomaj-cli ... --update --bank alu

Plugins
=======

BioMAJ support python plugins to manage custom downloads where supported protocols
are not enough (http page with unformatted listing, access to protected pages, etc.).

Example of plugins and how to configure them are available on [biomaj-plugins](https://github.com/genouest/biomaj-plugins) repository.

Plugins can define a specific way to:

* retreive release
* list remote files to download
* download remote files

Plugin can define one or many of those features.

Basically, one defined in bank property file:

    # Location of plugins
    plugins_dir=/opt/biomaj-plugins
    # Use plugin to fetch release
    release.plugin=github
    # List of arguments of plugin function with key=value format, comma separated
    release.plugin_args=repo=osallou/goterra-cli

Plugins are used when related workflow step is used:

* release.plugin <= returns remote release
* remote.plugin <= returns list of files to download
* download.plugin <= download files from list of files

API documentation
=================

https://readthedocs.org/projects/biomaj/

Status
======

[![Build Status](https://travis-ci.org/genouest/biomaj.svg?branch=master)](https://travis-ci.org/genouest/biomaj)

[![Documentation Status](https://readthedocs.org/projects/biomaj/badge/?version=latest)](https://readthedocs.org/projects/biomaj/?badge=latest)

[![Code Health](https://landscape.io/github/genouest/biomaj/master/landscape.svg?style=flat)](https://landscape.io/github/genouest/biomaj/master)

Testing
=======

Execute unit tests

    nosetests

Execute unit tests but disable ones needing network access

    nosetests -a '!network'

Monitoring
==========

InfluxDB (optional) can be used to monitor biomaj. Following series are available:

* biomaj.banks.quantity (number of banks)
* biomaj.production.size.total (size of all production directories)
* biomaj.workflow.duration (workflow duration)
* biomaj.production.size.latest (size of latest update)
* biomaj.bank.update.downloaded_files (number of downloaded files)
* biomaj.bank.update.new (track updates)

*WARNING* Influxdb database must be created, biomaj does not create the database (see https://docs.influxdata.com/influxdb/v1.6/query_language/database_management/#create-database)

License
=======

A-GPL v3+

Remarks
=======

To delete elasticsearch index:

 curl -XDELETE '<http://localhost:9200/biomaj_test/'>

Credits
=======

Special thanks for tuco at Pasteur Institute for the intensive testing and new ideas.
Thanks to the old BioMAJ team for the work they have done.

BioMAJ is developped at IRISA research institute.
