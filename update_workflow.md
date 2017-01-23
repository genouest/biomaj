---
title: Workflow
layout: default
---

A bank is updated only under certain conditions and configuration

if fromscratch option is set, bank is fully updated in any case

Get release from remote server

```
    If release.file not empty:
      Get remote file matching regular expression
      if release.regexp not empty:
        Extract release from file with regexp
      if release.file contains match expression like myfile_(\d+).txt:
        Extract release from file name
      else no_release
    else no_release
```

If no_release

```
    get release from last updated file dae
```

if release could be extracted:

```
    if last session was successful (no update needed or full updated completed)
      if release in existing production directories
         do not update
      else update
    else
      if failure occured in download
        update
```

Once release is determined, files are downloaded in offline directory and optionally uncompressed.
Then local files regular expression is matched against files in offline directory.
All files matching regular expression are copied to the release directroy in a subdirectory named **flat**

# Workflow

An update workflow is made on the following steps

  init

    Initialisation of the bank

  check

    Various checks...

  depends

    Bank dependencies, if any, update dependency banks first

  preprocess

    Execute pre processes

  release

    Try to get release from remote server

  download => uncompress => copy

    If previous step did not found any release, get one from latest updated file
    Find files to download and download them in offline directory
    Optionally uncompress files
    Copy files from offline dir to production dir, matching local regexp

  postprocess => metadata => stats

    Execute postprocesses, settings environment variables
    Extract metadata information for processes output files (stdout)
    Compute statistics on downloaded/process generated files

  publish => clean_offline => delete_old => clean_old_sessions

    If publish, set current release as **current** production directory
    Clean offline directory
    Check if old production directories should be removed and remove them, **current** and freezed production directories cannot be deleted

    Clean old sessions (not linked to a production directory)

  over

    Remove lock, save session etc..
