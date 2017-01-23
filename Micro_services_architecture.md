---
title: Microservices
layout: default
---

# Micro services

## About

Feature is available from version 3.1

Biomaj was a monolithic application. Goal is to split the application in multiple specialized components.
Once split, Biomaj will still be usable/callable in monolithic mode for single server/local user usage.
However, if deployed in micro service mode, all components can be scaled independently to face the load/updates.

For example, it is possible to launch 3 instances of the download component to handle, at maximum 3 parrallel downloads, whatever the number of banks being updated at the same time. All updates will share the same download components, and waiting downloads will simply be queued and dispatched to the components. At any time, components can be scaled up or down with automatic registration.

Biomaj client can also request update/status etc.. from a remote server with his credentials.


## Architecture


[https://drive.google.com/open?id=0B-1RyLsumsUwWHZnMVhhRFdscUk](https://drive.google.com/open?id=0B-1RyLsumsUwWHZnMVhhRFdscUk)


## Deploying

Micro services can be deployed on one or many servers. each component is deployed and configured independantly.

Install biomaj-cli python package on server that will execute biomaj commands once BioMAJ is deployed

    pip install biomaj-cli

## Directory structure

Microservices provide BioMAJ with pre-configuration. It expects the following directory struture under biomaj directory:

    biomaj |
           -> conf
           -> lock
           -> db
           -> cache
           -> process
           -> log


## With Docker

### Requirements

You need Docker and docker-compose.
To deploy on multiple servers, you should use swarm to dispatch services on multiple nodes.
On multi-node configuration, biomaj-docker directory should be accessible on all nodes, as well as biomaj conf and data directory.

### Configuration

Docker microservices are auto-configured. To override default configuration you can add biomaj-config volume to /etc/biomaj and modify property files in biomaj-config, example:

    biomaj-download-message:
        image: osallou/biomaj-test
        volumes:
            - ${BIOMAJ_DIR}/biomaj:/var/lib/biomaj/data
            - ${BIOMAJ_DIR}/biomaj-config:/etc/biomaj
        environment:
            - BIOMAJ_USER_PASSWORD=${BIOMAJ_USER_PASSWORD}
            - BIOMAJ_CONFIG=/etc/biomaj/config.yml
            - REDIS_PREFIX=biomajdownload
            - RABBITMQ_USER=biomaj

Or you can redefine global.properties config variables with environment variables with syntax BIOMAJ_X_Y_Z for variable x.y.z, example:


    biomaj-daemon-message:
        image: osallou/biomaj-test
        volumes:
            - ${BIOMAJ_DIR}/biomaj:/var/lib/biomaj/data
        environment:
            - BIOMAJ_USER_PASSWORD=${BIOMAJ_USER_PASSWORD}
            - BIOMAJ_CONFIG=/etc/biomaj/config.yml
            - REDIS_PREFIX=biomajdaemon
            - RABBITMQ_USER=biomaj
            - RABBITMQ_PASSWORD=biomaj
            - BIOMAJ_USE_LDAP=1
            - BIOMAJ_LDAP_HOST=my.ldap.org
        ....


Most configuration variables from config.yml can be overriden with environment variables (see  def service_config_override of biomaj-core), for example

    WEB_PORT=5010

### Deploy

To ease the install, you can configure BIOMAJ_DIR (see below) to be a subdirectory of biomaj-docker (https://github.com/genouest/biomaj-docker) cloned repository

    cd path_to_biomaj_install_dir
    git clone https://github.com/genouest/biomaj-docker
    cd biomaj-docker
    # edit .env file, replace path_to_biomaj_dir to location where biomaj config and data will be installed
    # path_to_biomaj_dir must be shared/accessible on all biomaj instances
    echo "BIOMAJ_DIR=path_to_biomaj_dir" > .env
    # Start services
    docker-compose up -d

You can then scale the number of service:

    docker-compose scale biomaj-download-message=2

Services will start with default configuration. docker-compose.yml can be updated to add other volumes, default ports etc...

By default, databases and other services will use BIOMAJ_DIR subdirectories for persistence. If services are restarted, they will use those directories. Location can be updated in docker-compose.yml file.

biomaj-cli must use biomaj-public-proxy as endpoint (port 5000 by default):

    biomaj-cli.py --proxy http://biomaj-publix-proxy:5000 --api-key XYZ --update --bank alu

## From sources

For example resources (configuration), check at https://github.com/genouest/biomaj-docker

You need the following resources:

* redis server
* mongodb server
* rabbitmq server
* consul server
* prometheus server
* elasticsearch (optional)

Install web proxies (internal and external), you should use Docker as they use automatic reload of configuration based on running components (see docker-compose.yml for example configuration)

Install biomaj related package on hosts:

    pip install biomaj-daemon
    pip install biomaj-user
    pip install biomaj-download
    pip install biomaj-process
    pip install biomaj-cron (optional)
    pip install biomaj-ftp (optional)

For biomaj-watcher:

    git clone https://github.com/genouest/biomaj-watcher
    cd biomaj-watcher
    python setup.py develop

for each component, create a config.yml file based on example in biomaj-config and execute process:

    export BIOMAJ_CONFIG=my_process_config_file.yml
    COMMAND_TO_RUN

COMMAND_TO_RUN should be the command specified in docker-compose.yml for each component.

In my_process_config_file.yml, one should take care of setting correct url for each server (mongo, ...) as well as web/port (port on which component will listen to).

## Create users

If not using LDAP, you must create users that will interact with BioMAJ.
You can get back the api key fo the user with the --about-me option of the biomaj-cli once created.

Connect to a biomaj-user instance:

    docker exec -it BIOMAJUSER_INSTANCE_ID /bin/bash
    #biomaj-users --action create --user biomaj --email me@test.org --password 12345
    Will return created user with api-key


## Status

You can check services status at http://biomaj-public-proxy:5000/status

or using API

    curl http://biomaj-public-proxy:5000/api/daemon/status
