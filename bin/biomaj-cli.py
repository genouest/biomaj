#!/usr/bin/python

import os,sys
#from optparse import OptionParser
import argparse
import pkg_resources

from biomaj.bank import Bank
from biomaj.config import BiomajConfig
from biomaj.notify import Notify
from biomaj.options import Options

def main():

  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('-c', '--config', dest="config",help="Configuration file")
  parser.add_argument('--check', dest="check", help="Check bank property file", action="store_true", default=False)
  parser.add_argument('-u', '--update', dest="update", help="Update action", action="store_true", default=False)
  parser.add_argument('-z', '--fromscratch', dest="fromscratch", help="Force a new cycle update", action="store_true", default=False)
  parser.add_argument('-p', '--publish', dest="publish", help="Publish", action="store_true", default=False)
  parser.add_argument('--release', dest="release",help="release of the bank")
  parser.add_argument('--from-task', dest="from_task",help="Start cycle at a specific task (init always executed)")
  parser.add_argument('--process', dest="process",help="Linked to from-task, optionally specify a block, meta or process name to start from")
  parser.add_argument('-l', '--log', dest="log",help="log level")
  parser.add_argument('-r', '--remove', dest="remove", help="Remove a bank release", action="store_true", default=False)
  parser.add_argument('--remove-all', dest="removeall", help="Remove all bank releases and database records", action="store_true", default=False)
  parser.add_argument('-s', '--status', dest="status", help="Get status", action="store_true", default=False)
  parser.add_argument('-b', '--bank', dest="bank",help="bank name")
  parser.add_argument('--stop-before', dest="stop_before",help="Store workflow before task")
  parser.add_argument('--stop-after', dest="stop_after",help="Store workflow after task")
  parser.add_argument('--freeze', dest="freeze", help="Freeze a bank release", action="store_true", default=False)
  parser.add_argument('--unfreeze', dest="unfreeze", help="Unfreeze a bank release", action="store_true", default=False)
  parser.add_argument('-f', '--force', dest="force", help="Force action", action="store_true", default=False)
  parser.add_argument('-h', '--help', dest="help", help="Show usage", action="store_true", default=False)

  parser.add_argument('--search', dest="search", help="Search by format and types", action="store_true", default=False)
  parser.add_argument('--formats', dest="formats",help="List of formats to search, comma separated")
  parser.add_argument('--types', dest="types",help="List of types to search, comma separated")
  parser.add_argument('--query', dest="query",help="Lucene query syntax to search in index")

  parser.add_argument('--show', dest="show", help="Show format files for selected bank", action="store_true", default=False)

  parser.add_argument('--version', dest="version", help="Show version", action="store_true", default=False)


  options = Options()
  parser.parse_args(namespace=options)

  options.no_log = False

  if options.help:
    print '''
--config: global.properties file path

--status: list of banks with published release
    [OPTIONAL]
    --bank xx / bank: Get status details of bank

--log DEBUG|INFO|WARN|ERR  [OPTIONAL]: set log level in logs for this run, default is set in global.properties file
--check: Check bank property file
    [MANDATORY]
    --bank xx: name of the bank to check (will check xx.properties)
--update: Update bank
    [MANDATORY]
    --bank xx: name of the bank to update
    [OPTIONAL]
    --publish: after update set as *current* version
    --fromscratch: force a new update cycle, even if release is identical, release will be incremented like (myrel_1)
    --stop-before xx: stop update cycle before the start of step xx
    --stop-after xx: stop update cycle after step xx has completed
    --from-task xx --release yy: Force an re-update cycle for bank release *yy* or from current cycle (in production directories), skipping steps up to *xx*
    --process xx: linked to from-task, optionally specify a block, meta or process name to start from
--publish / publish: Publish bank as current release to use
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to publish

--remove-all: Remove all bank releases and database records
    [MANDATORY]
    --bank xx: name of the bank to update
    [OPTIONAL]
    --force: remove freezed releases
--remove: Remove bank release (files and database release)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

    Release must not be the *current* version. If this is the case, publish a new release before.

--freeze: Freeze bank release (cannot be removed)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

--unfreeze: Unfreeze bank release (can be removed)
    [MANDATORY]
    --bank xx: name of the bank to update
    --release xx: release of the bank to remove

--search: basic search in bank production releases, return list of banks
   --formats xx,yy : list of comma separated format
  AND/OR
   --types xx,yy : list of comma separated type

   --query "LUCENE query syntax": search in index (if activated)

--show: Show bank files per format
  [MANDATORY]
  --bank xx: name of the bank to show
  [OPTIONAL]
  --release xx: release of the bank to show
    '''
    return

  if options.version:
    version = pkg_resources.require('biomaj')[0].version
    print 'Version: '+str(version)
    return

  bmaj = None
  try:
    if options.config is not None:
      BiomajConfig.load_config(options.config)
    else:
      BiomajConfig.load_config()
  except Exception as e:
    print str(e)
    sys.exit(1)

  try:
    if options.search:
      if options.query:
        res = Bank.searchindex(options.query)
        print "Query matches for :"+options.query
        print "Release\tFormat\tType\tFiles\n"
        for match in res:
          print match['_source']['release'] + "\t" + \
                str(match['_source']['format']) + "\t" + \
                str(match['_source']['types']) + "\n"
          for f in match['_source']['files']:
            print "\t\t\t"+f+"\n"
      else:
        formats = []
        if options.formats:
          formats = options.formats.split(',')
        types = []
        if options.types:
          types = options.types.split(',')
        print "Search by formats="+str(formats)+", types="+str(types)
        res = Bank.search(formats, types, False)
        print '#' * 80
        print "# Name\tRelease"
        for bank in res:

          print " "+bank['name']
          for prod in bank['production']:
              print " \t"+prod['release']+"\t"+','.join(prod['formats'])+"\t"+','.join(prod['types'])

        print '#' * 80
        return

    if options.show:
      if not options.bank:
        print "Bank option is required"
        sys.exit(1)

      bank = Bank(options.bank, no_log=False)
      for prod in bank.bank['production']:
        include = True
        if options.release and (prod['release'] != options.release and prod['prod_dir'] != options.release):
          include =False
        if include:
          session = bank.get_session_from_release(prod['release'])
          print '#' * 80
          print "# Name:\t"+bank.bank['name']
          print "# Release:\t"+prod['release']
          formats = session['formats']
          for fformat in formats.keys():
            print "# \tFormat:\t"+fformat
            for elt in formats[fformat]:
              print "# \t\tTypes:\t"+','.join(elt['types'])
              print "# \t\tTags:"
              for tag in elt['tags'].keys():
                print "# \t\t\t"+tag+":"+elt['tags'][tag]
              print "# \t\tFiles:"
              for file in elt['files']:
                print "# \t\t\t"+file
      sys.exit(1)

    if options.check and options.bank:
      bank = Bank(options.bank, no_log=False)
      print options.bank+" check: "+str(bank.check())+"\n"
      sys.exit(0)


    if options.status:
      if options.bank:
        bank = Bank(options.bank)
        _bank = bank.bank
        print '#' * 80
        print "# Name:\t"+_bank['name']
        print "# Type:\t"+str(_bank['properties']['type'])
        # Get last update session
        if 'status' in _bank:
          print "# Last update status:\t"+str(_bank['status']['over']['status'])
        release = None
        if 'current' in _bank and _bank['current']:
          for prod in _bank['production']:
            if _bank['current'] == prod['session']:
              release = prod['release']
        print "# Published release:\t"+str(release)
        print "# Production directories"
        for prod in _bank['production']:
          if 'freeze' in prod:
            print "#\tFreeze:\t"+str(prod['freeze'])
          print "#\tRemote release:\t"+prod['remoterelease']
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
          print " "+bank['name']+"\t"+','.join(bank['properties']['type'])+"\t"+str(release)
        print '#' * 80
        return

    if options.update and options.bank:
      bmaj = Bank(options.bank, options)
      print 'Log file: '+bmaj.config.log_file
      res = bmaj.update()
      Notify.notifyBankAction(bmaj)
      if not res:
        sys.exit(1)

    if options.freeze and options.release and options.bank:
      bmaj = Bank(options.bank, options)
      res = bmaj.freeze(options.release)
      if not res:
        sys.exit(1)

    if options.unfreeze and options.release and options.bank:
      bmaj = Bank(options.bank, options)
      res = bmaj.unfreeze(options.release)
      if not res:
        sys.exit(1)

    if ((options.remove and options.release) or options.removeall) and options.bank:
      bmaj = Bank(options.bank, options, no_log=True)
      print 'Log file: '+bmaj.config.log_file
      if options.removeall:
        res = bmaj.removeAll(options.force)
      else:
        res = bmaj.remove(options.release)
        Notify.notifyBankAction(bmaj)
      if not res:
        sys.exit(1)

    if options.publish:
      if not options.bank:
        print "Bank name or release is missing"
        sys.exit(1)
      bmaj = Bank(options.bank, options)
      print 'Log file: '+bmaj.config.log_file
      bmaj.load_session()
      bank = bmaj.bank
      session = None
      if options.get_option('release') is None:
        # Get latest prod release
        if len(bank['production'])>0:
          prod = bank['production'][len(bank['production'])-1]
          for s in bank['sessions']:
            if s['id'] == prod['session']:
              session = s
              break
      else:
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
      bmaj.session._session = session
      bmaj.publish()
  except Exception as e:
    print str(e)

if __name__ == '__main__':
    main()
