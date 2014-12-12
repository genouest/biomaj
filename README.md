BioMAJ
=====

This project is a complete rewrite of BioMAJ (http://biomaj.genouest.org).

It is in development

Dependencies
============

libcurl-dev

mongodb, elasticsearch (use_elastic=1)

ElasticSearch add advanced search features to biomaj.

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
