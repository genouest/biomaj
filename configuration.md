---
title: Configuration
layout: default
---

# Global properties

The main configuration, shared by all banks, is in the *global.properties* file. It can also be superseeded by a file in user home directory *~/.biomaj.cfg* (optional).

From API, file can be specified with BiomajConfig.load_config(path_to_config)


## Mandatory parameters

```
[GENERAL]
conf.dir=/etc/biomaj/db_properties
log.dir=/var/log/biomaj
process.dir=/usr/share/biomaj/conf/process
#The root directory where all databases are stored.
#If your data is not stored under one directory hierarchy
#you can override this value in the database properties file.
data.dir=/var/lib/biomaj
# Optional, lock file directory, defaults to data.dir
lock.dir=/var/lib/biomaj/lock
cache.dir=/var/cache/biomaj

db.url=mongodb://localhost:27017
db.name=biomaj


```

## Optional parameters

```
# separator between bank name and release for directory
# underscore as default
# biomaj >= 3.0.16
release.separator = _

# List of user admin (linux user id, comma separated)
# biomaj >= 3.0.1
admin=

#Use sudo for Docker, default is 1 (else 0)
docker.sudo=1

#Allow LDAP authentication
use_ldap=0
ldap.host=localhost
ldap.port=389
ldap.dn=dc=example,dc=org

#Use ElasticSearch for index/search capabilities
use_elastic=1
#Comma separated list of elasticsearch nodes  host1,host2:port2
elastic_nodes=localhost
elastic_index=biomaj

# Auto publish on updates (do not need publish flag, can be overriden in bank property file)
auto_publish=0

# Background processing with Celery configuration (for biomaj watcher)
celery.queue=biomaj
celery.broker=mongodb://localhost:27017/biomaj_celery

#Get directory stats (can be time consuming depending on number of files etc...)
data.stats=1

#The historic log file is generated in log/
#define level information for output : DEBUG,INFO,WARN,ERR
historic.logfile.level=DEBUG

#----------------
# Mail Configuration
#---------------

#Uncomment thes lines if you want receive mail when the workflow is finished
mail.smtp.host=
mail.admin=
mail.from=

# Number of thread during the processes management
bank.num.threads=4

# Number of threads to use for downloading
# set to 0 for no limit in parallelization when using micro services
files.num.threads=4

#to keep more than one release increase this value
keep.old.version=0

# Optional: do not remove old sessions from database,when removing releases
# >= 3.0.15
# keep.old.sessions = 1
# Default: 0
keep.old.sessions=0

# Can be defined per bank
http.parse.dir.line=<img[\s]+src="[\S]+"[\s]+alt="\[DIR\]"[\s]*/?>[\s]*<a[\s]+href="([\S]+)/"[\s]*>.*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})
http.parse.file.line=<img[\s]+src="[\S]+"[\s]+alt="\[[\s]+\]"[\s]*/?>[\s]<a[\s]+href="([\S]+)".*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})[\s]+([\d\.]+[MKG]{0,1})

http.group.dir.name=1
http.group.dir.date=2
http.group.file.name=1
http.group.file.date=2
http.group.file.size=3
# Biomaj >= 3.0.18
# Optional date extract in HTTP protocol following python date regexp format (http://www.tutorialspoint.com/python/time_strptime.htm)
#http.group.file.date_format=%%d-%%b-%%Y %%H:%%M

# Bank default access
visibility.default=public

# Proxy, optional proxy (see format at http://curl.haxx.se/libcurl/c/CURLOPT_PROXY.html)
# Does not work for FTP as library maps FTP to HTTP and HTTP format will differ with proxies.
# biomaj >= 3.0.7
#proxy=myproxyhost:1080
#proxy=myproxyhost
# Set proxy authentication if any, else keep commented
#proxy_auth=user:password

```


## Deprecated options


```
# Computed banks
db.source => depends

#Link copy property
do.link.copy=true

#Needed if data sources are contains in an archive
log.files=true
local.files.excluded=\\.panfs.*

#---------------------
# PROTOCOL
#-------------------
port=21
username=anonymous
password=anonymous@nowhere.com

#access user for production directories
production.directory.chmod=775


```
# Bank configuration

Each bank owns its configuration file. It must be named **bank_name**.properties and located in *conf.dir*.
The bank configuration file can override any global configuration expect above mandatory parameters.

The update process takes into account the loast modified date of the bank config file. If file is updated, the whole process is restarted.

It is possible to define *variables* and reuse them in the property file, example:

    myvar=myvalue
    mysupervar=%(myvar)s/additional_value
    # properties can be called with the syntax  %(property_name)s

2 additional properties are available, set by the process itself when the remote release is determined, localrelease and remoterelease. remoterelease matches the release found for the current run, and localrelease matches the release used locally (ex. myversion or myversion__2).


```
db.fullname="my bank simple description"
# Should be the same than file name mybankname.properties
db.name=mybankname
# Information on the type(s) of the bank, comma separated
db.type=nucleic,protein

# Directory to use for download, must be relative to data.dir and must not start with a /
offline.dir.name=offline/mybankname_tmp
# Directory, relative to data.dir where bank release will be stored, must not start with a /
dir.version=test/mybankname



# Bank dependencies : depends=bankA,bankB
# dependent bank may themselves depend on other banks
depends=
# Optional
#bankA.files.move=**/*
#bankB.files.move=flat/file1 flat/file2

# Optional: If depends is set, optionally specify to use the release of a dependent bank
# eg ref.release=bankA  , new bank will have same release than latest bankA
ref.release=

# ftp, http, local, multi
# none: no expected file download (for computed banks for example), > 3.0.10
#       remote.files and local.files are not necessary in this case
#       however a release must be set (from dependent bank or via a release file)
protocol=ftp
# for non local remote server
# server=
server=ftp.ncbi.nih.gov
# Optional, credentials access to server, format= user:password
server.credentials=
# base url to search in, must start and end with a /
remote.dir=/blast/db/FASTA/

# Download timeout, in seconds.
# From version >=3.0.13
# If timeout is reached, retry the download. If fails again, exit with error
# Default: 24h
# Required if download freezes
timeout.download=300

# Optional
# release.protocol =
# release.server =
# release.url.method =
# release.url.params =
# release.remote.dir =
# release.format = "%Y-%m-%d"  >= 3.0.15
release.file=
release.regexp=


# No leading slash
# Can use **/* to download all files and directories
# From version >= 3.0.4, for ftp and http protocols, remote.files can include groups to save file without directory structure, or partial directories only, examples:
# remote.files = genomes/fasta/.*\.gz => save files in offline directory, keeping remote structure offlinedir/genomes/fasta/
# remote.files = genomes/fasta/(.*\.gz) => save files in offline directory offlinedir/
# remote.files = genomes/(fasta)/(.*\.gz) => save files in offline directory offlinedir/fasta
# To manage a regexp selection but not use it as final file structure, prepend with :?
# Example: remote.files = genomes/(?:fasta|flat)/.*\.gz => take directories fasta or flat but keep original structure when saving file.
remote.files=^alu.*\.gz$

# Download files using specified file instead of listing remote.dir with remote.files
# From version >= 3.0.20
# remote.files will not be used to match files on remote server
# remote.list is a json text file with format, see Remote file list chapter
# If set, remote.files should be empty
# remote.list = path_to_file.json


# regexp to copy from downloaded files to production directory
# No leading slash
local.files=^alu\.(a|n).*


#Uncomment if you don't want to extract the data files.
#no.extract=true
```


## Release file properties

To extract release from a remote server

```
# File path to release, optionally with regular expression to find file. If regexp is set and release.regexp is not set, extract release from expression in file name
# For this to work, the definition of regexp for release.file needs to start with '^' and end with '$'
# release.file=^filename_release_is_(\d+)_\.txt$
release.file=
# if file is not a regexp, extract release from regexp in downloaded file
release.regexp=
# DEPRECATED release.file.compressed=

[optional, will use by default protocol, server, remote.dir]
release.protocol=
release.server=
release.remote.dir=
```

## Multiple files and direct download

It is possible to define directly some URLS to download, and to define multiple ones in a single bank.
Direct HTTP and FTP may cause a complete redownload at each update because last modification date may not been retreived from remote server.

When *multi* is used, only directftp and directhttp protocols are available for files to download.

remote.file.x.protocol, remote.file.x.server, remote.file.x.credentials are optional, if not set protocol, credentials and server properties are used.

```

protocol = directhttp
=> http://test.org/test/test.fa
server = test.org
remote.dir = test/test.fa
# GET or POST
# Optional, default = GET
url.method = GET
# Optional, save results as mytest.fa
target.name = mytest.fa

protocol = directhttp
=> http://test.org/test/test.fa?key1=val1,key2=val2
server = test.org
remote.dir = test/test.fa
# GET or POST
# Optional, default = GET
url.method = GET
url.params=key1,key2
key1.value=val1
key2.value=val1
# Optional, save results as mytest.fa
target.name = mytest.fa




protocol = directftp
=> ftp://test.org/test/test.fa
server = test.org
remote.dir = test/test.fa

protocol = multi
=> ftp://ftp.ncbi.org//musmusculus/chr1/chr1.fa
remote.file.0.protocol = directftp
remote.file.0.server = ftp.ncbi.org
remote.file.0.path = /musmusculus/chr1/chr1.fa

=> http://ftp2.fr.debian.org/debian/README.html?key1=value&key2=value2
remote.file.1.protocol = directhttp
remote.file.1.server = ftp2.fr.debian.org
remote.file.1.path = debian/README.html
# optional, save file under specified name/path
remote.file.1.name = debian/README.html
remote.file.1.method =  GET
remote.file.1.params.keys = key1,key2
remote.file.1.params.key1 = value1
remote.file.1.params.key2 = value2

=> http://ftp2.fr.debian.org/debian/README.html
    #POST PARAMS:
        key1=value
        key2=value2
remote.file.1.protocol = directhttp
remote.file.1.server = ftp2.fr.debian.org
# optional
remote.file.1.credentials = anonymous:password
remote.file.1.path = debian/README.html
# optional, save file under specified name/path
remote.file.1.name = debian/README.html
remote.file.1.method =  POST
remote.file.1.params.keys = key1,key2
remote.file.1.params.key1 = value1
remote.file.1.params.key2 = value2
```

Example of directhttp for a release file ( >= 3.10):

```
release.protocol=directhttp
release.server=plasmodb.org
# For directhttp, remote.dir contains full url
release.remote.dir=common/downloads/Current_Release/Build_number
# Mandatory: save remote url under name release.file
release.file=Build_number
release.regexp=(\d+)
```

## Remote file list (biomaj >= 3.0.20)

It is possible to extract with a preprocess a list of files to download, using defined protocol, server etc.
This file must be generated in json format

    remote.list = path_to_file.json

Structure of the file must be compliant with the following definition:


    [{"name": "alu.n.gz", "root": "/blast/db/FASTA/"}, {"name": "alu.n.gz.md5", "root": "/blast/db/FASTA/"}]


More information can be defined:


    [{"save_as": "alu.n.gz", "group": "ftp", "name": "alu.n.gz", "month": 11, "user": "anonymous", "year": 2003, "hash": "027577640cd7f182826abbf83e76050c", "permissions": "-r--r--r--", "root": "/blast/db/FASTA/", "day": 26, "size": 24465}, {"save_as": "alu.n.gz.md5", "group": "ftp", "name": "alu.n.gz.md5", "month": 6, "user": "anonymous", "year": 2009, "hash": "98caf48b2f98cdf0c38bda8a74352266", "permissions": "-r--r--r--", "root": "/blast/db/FASTA/", "day": 15, "size": 43}]


Each additional field is optional.

If year AND month AND day are not defined, then release parameters must be defined in the properties to extract a release information. If not present, they will be set to current date, so a new release will be detected each day.
If file is deleted by a post-process, then, at next run, file will not be detected and BioMAJ will consider there is no new release.
