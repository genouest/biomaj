from biomaj.schema_version import SchemaVersion
import argparse
import logging
import sys


desc = "Add or update a property to bank properties"
epilog = "Author: Emmanuel Quevillon (tuco@pasteur.fr)"
parser = argparse.ArgumentParser(description=desc, epilog=epilog)
parser.add_argument('-b', '--bank', action="store", dest="bank", default=None,
                    help="Bank name to update")
parser.add_argument('-c', '--cfgkey', action="store", dest="cfg", default=None,
                    help="Bank configuration key to retrieve prop value")
parser.add_argument('-p', '--property', action="store", dest="prop",
                    required=True, help="Property name")
parser.add_argument('-v', '--value', action="store", dest="value",
                    help="Property value")
args = parser.parse_args()
if sys.argv == 1:
    parser.print_help()
    sys.exit(0)
if args.value and args.cfg:
    logging.error("-v and -c are not compatible")
    sys.exit(1)
logging.warn("Needs global.properties in local directory or env variable BIOMAJ_CONF")
SchemaVersion.add_property(bank=args.bank, prop=args.prop, value=args.value,
                           cfg=args.cfg)
logging.info("Insertion done")
sys.exit(0)
                 
