***************
Advanced Topics
***************

LDAP
====

The `BioMAJ watcher <https://github.com/genouest/biomaj-watcher>`__,
provides an optional web interface to manage banks. Users can create
"private" banks and manage them via the web.

ElasticSearch
=============

In order to use the ``--search`` flag, you may wish to connect an
ElasticSearch cluster.

You will need to edit your ``global.properties`` to indicate where the ES servers are:

.. code:: ini

    use_elastic=0
    #Comma separated list of elasticsearch nodes  host1,host2:port2
    elastic_nodes=localhost
    elastic_index=biomaj
    # Calculate data.dir size stats
    data.stats=1

An example ``docker-compose.yml`` would use this:

.. literalinclude:: docker-compose-advanced.yml
   :language: yaml

And a modified ``global.properties`` referenced in that file would enable elasticsearch:

.. literalinclude:: global.advanced.properties
   :language: ini
