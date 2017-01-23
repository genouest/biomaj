---
title: Metrics and anlaysis
layout: default
---


# Prometheus
In micro service setup, biomaj provides metrics help with Prometheus (https://prometheus.io).
It gives information on banks updates, downloads time and size, process execution time etc...

Prometheus configuration example in biomaj-docker repository under biomaj-config/prometheus.yml

Prometheus are for *recent* statistics, not for long term statistics storage.

You can use Grafana or equivalent to get an admin dashboard.

# Influxdb

Biomaj optionally supports InfluxDB (time series database). It gathers some long term statistics on bank updates.

You can use Grafana or equivalent to get an admin dashboard.

# Zipkin

With a zipkin server (http://zipkin.io/) , with the --trace option, you can visualize your workflow execution with timing and result info. You get a detailled view of workflow decomposition, which component calls witch component, how much time it took to execute. It provides usefull information for debug and understand your bank update.

# With docker

The biomaj-docker repository gives the possibility to launch prometheus and zipkin servers along your biomaj install.
