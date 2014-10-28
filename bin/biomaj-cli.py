#!/usr/bin/python

import os,sys
from optparse import OptionParser

from biomaj.bank import Bank
from biomaj.config import BiomajConfig
from biomaj.notify import Notify

def main():

  parser = OptionParser()
  parser.add_option('-c', '--config', dest="config",help="Configuration file")
  parser.add_option('-u', '--update', dest="update", help="Update action", action="store_true", default=False)
  parser.add_option('--publish', dest="publish", help="Publish", action="store_true", default=False)
  parser.add_option('--release', dest="release",help="release of the bank")
  parser.add_option('-r', '--remove', dest="update", help="Update action", action="store_true", default=False)
  parser.add_option('-s', '--status', dest="status", help="Get status", action="store_true", default=False)
  parser.add_option('-b', '--bank', dest="bank",help="bank name")

  (options, args) = parser.parse_args()

  bmaj = None
  if options.config is not None:
    BiomajConfig.load_config(options.config)

  if options.status:
    if options.bank:
      bank = Bank(options.bank)
      _bank = bank.bank
      print '#' * 80
      print "# Name:\t"+_bank['name']
      print "# Type:\t"+_bank['type']
      release = None
      if 'current' in _bank and _bank['current']:
        for prod in _bank['production']:
          if _bank['current'] == prod['session']:
            release = prod['release']
      print "# Published release:\t"+str(release)
      print "# Production directories"
      for prod in _bank['production']:
        print "#\tRelease:\t"+prod['release']
        print "#\t\tSession:\t"+str(prod['session'])
        release_dir = os.path.join(bank.config.get('data.dir'),
                      bank.config.get('dir.version'),
                      prod['prod_dir'])
        print "#\t\tDirectory:\t"+release_dir
      print '#' * 80
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
          for prod in bank['production']:
            if bank['current'] == prod['session']:
              release = prod['release']
        else:
          release = None
        print " "+bank['name']+"\t"+bank['type']+"\t"+str(release)
      print '#' * 80
      return

  if options.update and options.bank:
    bmaj = Bank(options.bank, options)
    res = bmaj.update()
    Notify.notifyBankAction(bmaj)
    if not res:
      sys.exit(1)

  if options.publish:
    if not options.bank or not options.release:
      print "Bank name or release is missing"
      sys.exit(1)
    bmaj = Bank(options.bank, options)
    bmaj.load_session()
    bank = bmaj.bank
    session = None
    # Search production release matching release
    for prod in bank['production']:
      if prod['release'] == options.release or prod['prod_dir'] == options.release:
        # Search session related to this production release
        for s in bank['sessions']:
          if s['id'] == prod['session']:
            session = s
            break
        break
    if session is None:
      print "No production session could be found for this release"
      sys.exit(1)
    bank.session._session = session
    bank.publish()

if __name__ == '__main__':
    main()
