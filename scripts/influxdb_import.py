'''
Import biomaj banks statistics in Influxdb if never done before.....
'''
from influxdb import InfluxDBClient
from biomaj.bank import Bank
from biomaj_core.config import BiomajConfig
import sys

if len(sys.argv) != 2:
    print('Usage: influxdb_import.py path_to_global.properties')
    sys.exit(1)

BiomajConfig.load_config(config_file=sys.argv[1])

influxdb = None
try:
    influxdb = InfluxDBClient(host='biomaj-influxdb', database='biomaj')
except Exception as e:
    print('Failed to connect to influxdb, check configuration in global.properties: ' + str(e))
    sys.exit(1)

res = influxdb.query('select last("value") from "biomaj.banks.quantity"')
if res:
    print('Found data in influxdb, update info....')

banks = Bank.list()
nb_banks = 0
metrics = []
for bank in banks:
    productions = bank['production']
    total_size = 0
    latest_size = 0
    if not productions:
        continue
    nb_banks += 1
    latest_size = productions[len(productions) - 1]['size']
    for production in productions:
        if 'size' in production:
            total_size += production['size']

    influx_metric = {
            "measurement": 'biomaj.production.size.total',
            "fields": {
                "value": float(total_size)
            },
            "tags": {
                "bank": bank['name']
            },
            "time": int(production['session'])
    }
    metrics.append(influx_metric)
    influx_metric = {
            "measurement": 'biomaj.production.size.latest',
            "fields": {
                "value": float(latest_size)
            },
            "tags": {
                "bank": bank['name']
            },
            "time": int(production['session'])
    }
    metrics.append(influx_metric)
    influx_metric = {
                "measurement": 'biomaj.bank.update.new',
                "fields": {
                    "value": 1
                },
                "tags": {
                    "bank": bank['name']
                },
            "time": int(production['session'])
    }
    metrics.append(influx_metric)

influx_metric = {
     "measurement": 'biomaj.banks.quantity',
         "fields": {
             "value": nb_banks
             }
}
metrics.append(influx_metric)

influxdb.write_points(metrics, time_precision="s")
