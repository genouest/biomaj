BioMAJ3
=====

This project is a complete rewrite of BioMAJ (http://biomaj.genouest.org).

BioMAJ (BIOlogie Mise A Jour) is a workflow engine dedicated to data
synchronization and processing. The Software automates the update cycle and the
supervision of the locally mirrored databank repository.

Common usages are to download remote databanks (Genbank for example) and apply
some transformations (blast indexing, emboss indexing,...). Any script can be
applied on downloaded data. When all treatments are successfully applied, bank
is put in "production" on a dedicated release directory.
With cron tasks, update tasks can be executed at regular interval, data are
downloaded again only if a change is detected.

More documentation is available in wiki page.

Getting started
===============

Edit global.properties file to match your settings. Minimal conf are database connection and directories.

    biomaj-cli.py -h

    biomaj-cli.py --config global.properties --status

    biomaj-cli.py --config global.properties  --bank alu --update

Migration
=========

To migrate from previous BioMAJ, a script is available at:
https://github.com/genouest/biomaj-migrate. Script will import old database to
the new database, and update configuration files to the modified format. Data directory is the same.

Application Features
====================

* Synchronisation:
 * Multiple remote protocols (ftp, sftp, http, local copy, ....)
 * Data transfers integrity check
 * Release versioning using a incremental approach
 * Multi threading
 * Data extraction (gzip, tar, bzip)
 * Data tree directory normalisation


* Pre &Post processing :
 * Advanced workflow description (D.A.G)
 * Post-process indexation for various bioinformatics software (blast, srs,
   fastacmd, readseq, etc…)
 * Easy integration of personal scripts for bank post-processing automation


* Supervision:
 * Optional Administration web interface (biomaj-watcher)
 * CLI management
 * Mail alerts for the update cycle supervision



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

ElasticSearch indexing add advanced search features to biomaj to find bank
having files with specific format etc...
Configuration of ElasticSearch is not in the scope of BioMAJ documentation.
For a basic installation, one instance of ElasticSearch is enough (low volume of
data), in such a case, the ElasticSearch configuration file should be modified
accordingly:

    node.name: "biomaj" (or any other name)
    index.number_of_shards: 1
    index.number_of_replicas: 0

Installation
============

After dependencies installation, go in BioMAJ source directory:

    python setup.py install


You should consider using a Python virtual environment (virtualenv) to install BioMAJ.

In tools/examples, copy the global.properties and update it to match your local
installation.

The tools/process contains example process files (python and shell).

Docker
======

You can use BioMAJ with Docker (genouest/biomaj)


    docker pull genouest/biomaj
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

License
=======

A-GPL v3+

Remarks
=======

Biomaj uses libcurl, for sftp libcurl must be compiled with sftp support

To delete elasticsearch index:

 curl -XDELETE 'http://localhost:9200/biomaj_test/'

Credits
======

Special thanks for tuco at Pasteur Institute for the intensive testing and new
ideas....
Thanks to the old BioMAJ team for the work they have done.

BioMAJ is developped at IRISA research institute.
