---
title: About
layout: default
---

# Application Features

Synchronisation :

* Multiple remote protocols (ftp, sftp, http, local copy, ...)
* Data transfers integrity check
* Release versioning using a incremental approach
* Multi threading
* Data extraction (gzip, tar, bzip)
* Data tree directory normalisation
* Pre &Post processing :
  * Advanced workflow description (D.A.G) using Easy normalized syntax language
  * Post-process indexation for various bioinformatics software (blast, srs, fastacmd, readseq, etc…)
  * Easy integration of personal scripts for bank post-processing automation
  * DRMAA cluster integration
* Supervision :
  * Administration web interface (biomaj-watcher)
    * Web access to logs
    * Click / Cron management of updates
  * CLI status
  * Prometheus and Influxdb optional statistics
* Repository statistics
* Mail alerts for the update cycle supervision
* Search in available formats/types/tags/files (indexation)

# Why BioMAJ ?

Biological knowledge in a genomic or post-genomic context is mainly based on transitive bioinformatics analysis consisting in an iterative and periodic comparison of data newly produced against corpus of known information.

In large scale projects, this approach needs accurate bioinformatics software, pipelines, interfaces and numerous heterogeneous biological banks, which are distributed around the world. An integration process that consists in mirroring and indexing this data is obviously an essential preliminary step but represents a major challenge and a bottleneck in most bioinformatics projects; BioMAJ addresses this problem by proposing a flexible and robust automated environment.
