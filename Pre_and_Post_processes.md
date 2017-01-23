---
title: Processes
layout: default
---

# Processes

Processes can be executed locally, via DRMAA on a cluster, or locally in a Docker container (experimental but functional).

## Postprocesses

Post processes are defined in conf via BLOCKS property.

BLOCKS defines some META processes. Each block is executed sequentially
META processes are executed in parallel.

Each META define a list of process to execute sequentially.

By default, 2 threads are defined for parallel execution.

    BLOCKS=BLOCK1,BLOCK2
    BLOCK1.db.post.process=META0
    BLOCK2.db.post.process=META1,META2,META3
    META0=PROC0
    META1=PROC1,PROC2
    META2=PROC3
    META3=PROC4,PROC5

    PROC0.name=test0
    PROC0.desc=sample test
    # Execute locally or on DRMAA compliant cluster
    # Warning: if set to true, DRMAA_LIBRARY_PATH must be in set when executing biomaj
    # For example: export DRMAA_LIBRARY_PATH=/data1/sge/lib/lx24-amd64/libdrmaa.so
    PROC0.cluster=false

    # Execute process in a Docker container
    # BioMAJ env variables are sent to container, workdir is set to the current bank release directory
    # A shared directory is added on data.dir property (same value)
    # This is exclusive with cluster option.
    # Execution includes a Docker pull of the image
    # User executing must be able to sudo Docker (if set in global conf) or execute Docker
    #PROC0.docker=centos

    PROC0.type=test
    # Command to execute, in process.dir or path
    PROC0.exe=echo
    # Arguments
    PROC0.args=test $datadir
    # Expand shell variables (default true)
    PROC0.expand=true
    #[OPTIONAL]
    # If cluster is true, native DRMAA options (queue etc..)
    PROC0.native = -q myqueue
    # if those properties are set, commands ##BIOMAJ#...
    # will use the values given below for format/types/tags to allow the use of generic scripts, only
    # specifying the list of files generated (or only format with files,...)
    PROC0.format=blast
    PROC0.types=nucleic
    PROC0.tags=chr:chr1,organism:hg19
    # If files is set, then the post-process does not have to print generated files on STDOUT (but can)
    # in this case, the list of files will be extracted from this list with above format/types/tags
    PROC0.files=dir1/file1,dir1.file2


## Preprocesses and Removeprocesses

Preproccesses and removeprocesses are identical except there is no BLOCK.
META processes are defined via db.pre.process and db.remove.process properties

# Env variables

The following env variables are available in executed scripts

        dbname: bank name
        datadir: root directory for all production directories
        offlinedir: temporary directory
        dirversion: production directory for the bank containing all versions already 
                    downloaded and the future version. 
        #DEPRECATED remotedir: remote server directory
        noextract: Boolean telling whether the downloaded files are extracted
        #DEPRECATED localfiles: downloaded files that will be available during production
        #DEPRECATED remotefiles: regular expression for downloaded files
        mailadmin: administration mail
        mailsmtp: smtp server for sending mail
        localrelease: directory of the release in dirversion
        remoterelease: version number (available only for post­processes)
        removedrelease: removed version number (available only for remove processes)
        ...source: in case of virtual bank, path to the dependant bank (genbanksource if 
        depends on genbank)
        logdir: directory of logs for bank session  # biomaj >= 3.0.6
        logfile: log file for bank session # biomaj >= 3.0.6

# Metadata

Process can add metadata to the current release by write special lines to stdout.
This can add format, tags and files as additional information to the bank.

Syntax:

  ##BIOMAJ#*format*#*list_of_types*#*list_of_key_value_tags*#*list_of_files*

Lists are separated by a comma. Path sould be relative to the release root directory. However, path itself is not used by BioMAJ but is only a value indexed and returned by BioMAJ. So files can be full path to an other directory, relative path or any name.

```
echo "##BIOMAJ#blast#nucleic#organism:hg19,chr:chr1#blast/chr1/chr1db"
echo "##BIOMAJ#blast#nucleic#organism:hg19,chr:chr2#blast/chr2/chr2db"

echo "any text"

echo "##BIOMAJ#fasta#proteic#organism:hg19#fasta/chr1.fa,fasta/chr2.fa"

```
