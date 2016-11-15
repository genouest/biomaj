***************
Getting Started
***************

For a very basic setup, you can configure a ``docker-compose.yml`` file to use
with `docker <https://www.docker.com/products/overview#install_the_platform>`__,
which is especially helpful when you are testing out BioMAJ.

Docker
======

.. literalinclude:: docker-compose.yml
   :language: yaml
   :linenos:

This configuration file defines a simple MongoDB instance which is used for
backend storage by BioMAJ, as well as the BioMAJ instance itself. Line 8
denotes that a folder named ``data`` in the current directory will be mounted
into the volume as storage. Any files downloaded by BioMAJ will appear in this
directory.

Running the ``--help`` command can be done easily:

.. code:: console

    $ docker-compose run --rm biomaj --help


Simple Configuration
====================

Once you've reached this point, you're ready to start configuring BioMAJ to
download datasets for you. Configuration files should go instead a folder
``conf`` inside the ``data`` folder in your current directory. As an example,
we will use this simple ALU configuration file:

.. literalinclude:: alu.properties
   :language: text
   :linenos:

The file can be broken down into a couple of sections:

- Metadata (lines 1-15)
- Remote Source (17-24)
- Release Information (26-30)
- Other

The metadata consists of things like where data should be stored, and how
to name it. The remote source describes where data is to be fetched from,
release information we will see in another example, and then there are a
few extra, miscellaneous options shown in this example config.

If you have copied the ``alu.properties`` file into ``./data/conf/alu.properties``, you are ready to download this database:

.. code:: console

    $ docker-compose run --rm biomaj --bank alu --update
    2016-08-24 21:43:15,276 INFO  [root][MainThread] Log file: /var/lib/biomaj/log/alu/1472074995.28/alu.log
    Log file: /var/lib/biomaj/log/alu/1472074995.28/alu.log
    ...

This command should complete successfully, and you will have some more files in ``./data/``:

.. code:: console

    $ find data
    data/conf/alu.properties
    data/data/ncbi/blast/alu/alu-2003-11-26/flat/alu.a
    data/data/ncbi/blast/alu/alu-2003-11-26/flat/alu.n
    data/cache/files_1472074995.29
    data/log/alu/1472074995.28/alu.log

The ``data/data`` directories contain your downloaded files. Additionally
a cache file exists and a job run log is contains data about what occurred
during the download and processing. Note that the files that appear are
``alu.a`` and ``alu.n``, instead of ``alu.a.gz`` and ``alu.n.gz``. By
having the option ``no.extract=true`` commented out on line 33, BioMAJ
automatically extracted the data for us.

The ``--status`` command will allow you to see the status of various databases you have downloaded.

.. code:: console

    $ docker-compose run --rm biomaj --bank alu --status
    +--------+-----------------+----------------------+---------------------+
    | Name   | Type(s)         | Last update status   | Published release   |
    |--------+-----------------+----------------------+---------------------|
    | alu    | nucleic_protein | 2016-08-24 21:58:14  | 2003-11-26          |
    +--------+-----------------+----------------------+---------------------+
    +---------------------+------------------+------------+----------------------------------------------------+----------+
    | Session             | Remote release   | Release    | Directory                                          | Freeze   |
    |---------------------+------------------+------------+----------------------------------------------------+----------|
    | 2016-08-24 21:58:14 | 2003-11-26       | 2003-11-26 | /var/lib/biomaj/data/ncbi/blast/alu/alu-2003-11-26 | no       |
    +---------------------+------------------+------------+----------------------------------------------------+----------+


Advanced Configuration
======================

Once you have this sort of simple configuration working, you may wish to
explore more advanced configurations. There is a `public repository
<https://github.com/genouest/biomaj-data/>`__ of BioMAJ configurations which
will be interesting to the advanced user wishing to learn more about what can
be done with BioMAJ.
