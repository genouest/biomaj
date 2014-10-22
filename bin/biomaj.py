import os,sys
from optparse import OptionParser
import logging.config

from biomaj.bank import Bank

def main():

  parser = OptionParser()

  parser.add_option('-c', '--config', dest="config",help="Configuration file")
  parser.add_option('-u', '--update', dest="bank",help="Update a bank")
  parser.add_option('-s', '--status', dest="status", help="Get status", action="store_true", default=False)

  (options, args) = parser.parse_args()

  bmaj = None
  if options.config is not None:
    logging.config.fileConfig(options.config)
    Bank.load_config(options.config)


  if options.bank:
    bmaj = Bank(options.bank)
    bmaj.update()

if __name__ == '__main__':
    main()
