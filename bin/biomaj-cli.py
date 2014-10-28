#!/usr/bin/python

import os,sys
from optparse import OptionParser

from biomaj.bank import Bank
from biomaj.config import BiomajConfig

def main():

  parser = OptionParser()
  parser.add_option('-c', '--config', dest="config",help="Configuration file")
  parser.add_option('-u', '--update', dest="update", help="Update action", action="store_true", default=False)
  parser.add_option('-s', '--status', dest="status", help="Get status", action="store_true", default=False)
  parser.add_option('-b', '--bank', dest="bank",help="bank name")

  (options, args) = parser.parse_args()

  bmaj = None
  if options.config is not None:
    BiomajConfig.load_config(options.config)

  if options.status:
    if options.bank:
      bank = Bank(options.bank)
    else:
      print '#' * 80
      print "# Name\tType\tRelease"
      banks = Bank.list()
      for bank in banks:
        '''
        production = { 'release': self.session.get('release'),
                        'session': self.session._session['id'],
                        'data_dir': self.config.get('data.dir'),
                        'prod_dir': self.session.get_release_directory()}
        '''
        if 'current' in bank and bank['current']:
          for prod in production:
            if bank['current'] == prod['session']:
              release = prod['release']
        else:
          release = None
        print " "+bank['name']+"\t"+bank['type']+"\t"+str(release)
      print '#' * 80
      return

  if options.update and options.bank:
    bmaj = Bank(options.bank, options)
    return bmaj.update()

if __name__ == '__main__':
    main()
