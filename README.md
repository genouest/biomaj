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

Wiki page: https://github.com/osallou/biomaj/wiki

Migration
=========

To migrate from previous BioMAJ, a script is available at: https://github.com/osallou/biomaj-migrate

Application Features
====================

* Synchronisation:
 * Multiple remote protocols (ftp, sftp, http, local copy, ....)
 * Data transfers integrity check
 * Release versioning using a incremental approach
 * Multi threading
 * Data extraction (gzip, tar, bzip)
 * Data tree directory normalisation


*Pre &Post processing :
 * Advanced workflow description (D.A.G) 
 * Post-process indexation for various bioinformatics software (blast, srs,
   fastacmd, readseq, etc…)
 * Easy integration of personal scripts for bank post-processing automation


*Supervision:
 * Optional Administration web interface (biomaj-watcher)
 * CLI management
 * Mail alerts for the update cycle supervision



Dependencies
============


Packages:
 * Debian: libcurl-dev, libldap2-dev, gcc
 * CentOs: libcurl-devel, libldap-devel, gcc

Database:
 * mongodb (local or remote)

Indexing (optional):
 * elasticsearch (global property, use_elastic=1)

ElasticSearch indexing add advanced search features to biomaj to find bank
having files with specific format etc...

Status
======

[![Build Status](https://travis-ci.org/osallou/biomaj.svg?branch=master)](https://travis-ci.org/osallou/biomaj)

[![Coverage Status](https://coveralls.io/repos/osallou/biomaj/badge.png?branch=master)](https://coveralls.io/r/osallou/biomaj?branch=master)

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
