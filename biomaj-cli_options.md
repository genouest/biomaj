---
title: Client
layout: default
---

# Command line option

global.properties file is mandatory. If not specified, 'global.properties' will be searched in current directory or at BIOMAJ_CONF environment variable path (export BIOMAJ_CONF=/xx/yy/global.properties)

## description

```
--config: global.properties file path

--proxy: BioMAJ daemon url (http://x.y.z) [micro services only]

--trace: Trace workflow in Zipkin server

--api-key: User API key to authenticate against proxy [micro services only]

--whatsup: Get info on what biomaj is doing [micro services only]

--about-me: Get my info [micro services only]
    [MANDATORY]
    --proxy http://x.y.z
    --user-login XX
    --user-password XX

--update-status: get status of an update [micro services only]
    [MANDATORY]
    --bank xx: name of the bank to check
    --proxy http://x.y.z

--update-cancel: cancel current update [micro services only]
    [MANDATORY]
    --bank xx: name of the bank to cancel
    --proxy http://x.y.z


--check: Checks bank configuration
     [MANDATORY]
     --bank xx: bank name to check

--status: list of banks with published release
    [OPTIONAL]
    --bank xx / bank: Get status details of bank

--status-ko: list of banks in error status (last run)
  ( >= 3.0.14)

--log DEBUG|INFO|WARN|ERR  [OPTIONAL]: set log level in logs for this run, default is set in global.properties file

--update: Update bank
    [MANDATORY]
    --bank xx: name of the bank to update
    [OPTIONAL]
    --publish: after update set as *current* version
    --from-scratch: force a new update cycle, even if release is identical, release will be incremented like (myrel_1)
    --stop-before xx: stop update cycle before the start of step xx
    --stop-after xx: stop update cycle after step xx has completed
    --from-task xx --release yy: Force an re-update cycle for bank release *yy* or from current cycle (in production directories), skipping steps up to *xx*
    --process xx: linked to from-task, optionally specify a block, meta or process name to start from
    --release xx: release to update

--publish : Publish bank as current release to use
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to publish

--unpublish: Unpublish bank (remove current)
    [MANDATORY]
    --bank xx: name of the bank to update

--remove-all: Remove all bank releases and database records
    Remove processes are not executed, this deletes directly database and files content.
    [MANDATORY]
    --bank xx: name of the bank to update
    [OPTIONAL]
    --force: remove freezed releases

--remove-pending: Remove pending releases (Biomaj >= 3.0.6)
    [MANDATORY]
    --bank xx: name of the bank to update

--remove: Remove bank release (files and database release)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

    Release must not be the *current* version. If this is the case, publish a new release before.

--freeze: Freeze bank release (cannot be removed)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

--unfreeze: Unfreeze bank release (can be removed)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

--search: basic search in bank production releases, return list of banks
   --formats xx,yy : list of comma separated format
  AND/OR
   --types xx,yy : list of comma separated type
  OR
   --query "sometext or chr:chr1" : Lucene query syntax to query index
--show: Show bank files per format
  [MANDATORY]
  --bank xx: name of the bank to show
  [OPTIONAL]
  --release xx: release of the bank to show

--owner yy: Change owner fo the bank (user id), biomaj >= 3.0.1
    [MANDATORY]
    --bank xx: name of the bank

--change-dbname yy: Change name of the bank to this new name, biomaj >= 3.0.1
    [MANDATORY]
    --bank xx: current name of the bank

--move-production-directories yy: Change bank production directories location to this new path, path must exists, biomaj >= 3.0.1
    [MANDATORY]
    --bank xx: current name of the bank

--visibility public|private: change visibility public/private of a bank
    [MANDATORY]
    --bank xx: name of the bank

--maintenance on/off/status: (un)set biomaj in maintenance mode to prevent updates/removal

```


## Update workflow steps

 init, check, depends, preprocess, release, download, postprocess, publish, over
