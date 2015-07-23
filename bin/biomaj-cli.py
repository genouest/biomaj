#!/usr/bin/env python
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str
from tabulate import tabulate

import os,sys
#from optparse import OptionParser
import argparse
import pkg_resources
import configparser
import shutil

from biomaj.bank import Bank
from biomaj.config import BiomajConfig
from biomaj.notify import Notify
from biomaj.options import Options
from biomaj.workflow import Workflow

def main():

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', dest="config",help="Configuration file")
    parser.add_argument('--check', dest="check", help="Check bank property file", action="store_true", default=False)
    parser.add_argument('-u', '--update', dest="update", help="Update action", action="store_true", default=False)
    parser.add_argument('--fromscratch', dest="fromscratch", help="Force a new cycle update", action="store_true", default=False)
    parser.add_argument('-z', '--from-scratch', dest="fromscratch", help="Force a new cycle update", action="store_true", default=False)
    parser.add_argument('-p', '--publish', dest="publish", help="Publish", action="store_true", default=False)
    parser.add_argument('--unpublish', dest="unpublish", help="Unpublish", action="store_true", default=False)

    parser.add_argument('--release', dest="release",help="release of the bank")
    parser.add_argument('--from-task', dest="from_task",help="Start cycle at a specific task (init always executed)")
    parser.add_argument('--process', dest="process",help="Linked to from-task, optionally specify a block, meta or process name to start from")
    parser.add_argument('-l', '--log', dest="log",help="log level")
    parser.add_argument('-r', '--remove', dest="remove", help="Remove a bank release", action="store_true", default=False)
    parser.add_argument('--remove-all', dest="removeall", help="Remove all bank releases and database records", action="store_true", default=False)
    parser.add_argument('--remove-pending', dest="removepending", help="Remove pending release", action="store_true", default=False)
    parser.add_argument('-s', '--status', dest="status", help="Get status", action="store_true", default=False)
    parser.add_argument('-b', '--bank', dest="bank",help="bank name")
    parser.add_argument('--owner', dest="owner", help="change owner of the bank")
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

    parser.add_argument('-n', '--change-dbname', dest="newbank",help="Change old bank name to this new bank name")
    parser.add_argument('-e', '--move-production-directories', dest="newdir",help="Change bank production directories location to this new path, path must exists")
    parser.add_argument('--visibility', dest="visibility",help="visibility status of the bank")

    parser.add_argument('--maintenance', dest="maintenance",help="Maintenance mode (on/off/status)")

    parser.add_argument('--version', dest="version", help="Show version", action="store_true", default=False)


    options = Options()
    parser.parse_args(namespace=options)

    options.no_log = False

    if options.help:
        print('''
    --config: global.properties file path

    --status: list of banks with published release
        [OPTIONAL]
        --bank xx / bank: Get status details of bank

    --log DEBUG|INFO|WARN|ERR  [OPTIONAL]: set log level in logs for this run, default is set in global.properties file

    --check: Check bank property file
        [MANDATORY]
        --bank xx: name of the bank to check (will check xx.properties)

    --owner yy: Change owner of the bank (user id)
        [MANDATORY]
        --bank xx: name of the bank

    --visibility public|private: change visibility public/private of a bank
        [MANDATORY]
        --bank xx: name of the bank

    --change-dbname yy: Change name of the bank to this new name
        [MANDATORY]
        --bank xx: current name of the bank

    --move-production-directories yy: Change bank production directories location to this new path, path must exists
        [MANDATORY]
        --bank xx: current name of the bank

    --update: Update bank
        [MANDATORY]
        --bank xx: name of the bank(s) to update, comma separated
        [OPTIONAL]
        --publish: after update set as *current* version
        --from-scratch: force a new update cycle, even if release is identical, release will be incremented like (myrel_1)
        --stop-before xx: stop update cycle before the start of step xx
        --stop-after xx: stop update cycle after step xx has completed
        --from-task xx --release yy: Force an re-update cycle for bank release *yy* or from current cycle (in production directories), skipping steps up to *xx*
        --process xx: linked to from-task, optionally specify a block, meta or process name to start from
        --release xx: release to update

    --publish: Publish bank as current release to use
        [MANDATORY]
        --bank xx: name of the bank to update
        --release xx: release of the bank to publish
    --unpublish: Unpublish bank (remove current)
        [MANDATORY]
        --bank xx: name of the bank to update

    --remove-all: Remove all bank releases and database records
        [MANDATORY]
        --bank xx: name of the bank to update
        [OPTIONAL]
        --force: remove freezed releases

    --remove-pending: Remove pending releases
        [MANDATORY]
        --bank xx: name of the bank to update

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

    --maintenance on/off/status: (un)set biomaj in maintenance mode to prevent updates/removal

        ''')
        return

    if options.version:
        version = pkg_resources.require('biomaj')[0].version
        print('Version: '+str(version))
        return

    bmaj = None
    try:
        if options.config is not None:
            BiomajConfig.load_config(options.config)
        else:
            BiomajConfig.load_config()
    except Exception as e:
        print(str(e))
        sys.exit(1)

    try:

        if options.maintenance:
            if options.maintenance not in ['on', 'off', 'status']:
                print("Wrong maintenance value [on,off,status]")
                sys.exit(1)
            data_dir = BiomajConfig.global_config.get('GENERAL', 'data.dir')
            if BiomajConfig.global_config.has_option('GENERAL', 'lock.dir'):
                lock_dir = BiomajConfig.global_config.get('GENERAL', 'lock.dir')
            else:
                lock_dir = data_dir
            maintenance_lock_file = os.path.join(lock_dir,'biomaj.lock')
            if options.maintenance == 'status':
                if os.path.exists(maintenance_lock_file):
                    print("Maintenance: On")
                else:
                    print("Maintenance: Off")
                sys.exit(0)
            if options.maintenance == 'on':
                f = open(maintenance_lock_file, 'w')
                f.write('1')
                f.close()
                print("Maintenance set to On")
                sys.exit(0)
            if options.maintenance == 'off':
                if os.path.exists(maintenance_lock_file):
                    os.remove(maintenance_lock_file)
                print("Maintenance set to Off")
                sys.exit(0)


        if options.owner:
            if not options.bank:
                print("Bank option is missing")
                sys.exit(1)
            bank = Bank(options.bank, no_log=True)
            bank.set_owner(options.owner)
            sys.exit(0)

        if options.visibility:
            if not options.bank:
                print("Bank option is missing")
                sys.exit(1)
            if options.visibility not in ['public', 'private']:
                print("Valid values are public|private")
                sys.exit(1)
            bank = Bank(options.bank, no_log=True)
            bank.set_visibility(options.visibility)
            print("Do not forget to update accordingly the visibility.default parameter in the configuration file")
            sys.exit(0)

        if options.newdir:
            if not options.bank:
                print("Bank option is missing")
                sys.exit(1)
            if not os.path.exists(options.newdir):
                print("Destination directory does not exists")
            bank = Bank(options.bank, options= options, no_log=True)
            if not bank.bank['production']:
                print("Nothing to move, no production directory")
                sys.exit(0)
            bank.load_session(Workflow.FLOW, None)
            w = Workflow(bank)
            res = w.wf_init()
            if not res:
                sys.exit(1)
            for prod in bank.bank['production']:
                session = bank.get_session_from_release(prod['release'])
                bank.load_session(Workflow.FLOW, session)
                prod_path = bank.session.get_full_release_directory()
                if os.path.exists(prod_path):
                    shutil.move(prod_path, options.newdir)
                prod['data_dir'] = options.newdir
            bank.banks.update({'name': options.bank}, {'$set' : { 'production': bank.bank['production'] }})
            print("Bank production directories moved to " + options.newdir)
            print("WARNING: do not forget to update accordingly the data.dir and dir.version properties")
            w.wf_over()
            sys.exit(0)

        if options.newbank:
            if not options.bank:
                print("Bank option is missing")
                sys.exit(1)
            bank = Bank(options.bank, no_log=True)
            conf_dir = BiomajConfig.global_config.get('GENERAL', 'conf.dir')
            bank_prop_file = os.path.join(conf_dir,options.bank+'.properties')
            config_bank = configparser.SafeConfigParser()
            config_bank.read([os.path.join(conf_dir,options.bank+'.properties')])
            config_bank.set('GENERAL', 'db.name', options.newbank)
            newbank_prop_file = open(os.path.join(conf_dir,options.newbank+'.properties'),'w')
            config_bank.write(newbank_prop_file)
            newbank_prop_file.close()
            bank.banks.update({'name': options.bank}, {'$set' : { 'name': options.newbank }})
            os.remove(bank_prop_file)
            print("Bank "+options.bank+" renamed to "+options.newbank)
            sys.exit(0)

        if options.search:
            if options.query:
                res = Bank.searchindex(options.query)
                print("Query matches for :"+options.query)
                print("Release\tFormat\tType\tFiles\n")
                for match in res:
                    print(match['_source']['release'] + "\t" + \
                          str(match['_source']['format']) + "\t" + \
                          str(match['_source']['types']) + "\n")
                    for f in match['_source']['files']:
                        print("\t\t\t"+f+"\n")
            else:
                formats = []
                if options.formats:
                    formats = options.formats.split(',')
                types = []
                if options.types:
                    types = options.types.split(',')
                print("Search by formats="+str(formats)+", types="+str(types))
                res = Bank.search(formats, types, False)
                print('#' * 80)
                print("# Name\tRelease")
                for bank in res:
                    print(" "+bank['name'])
                    for prod in bank['production']:
                        iscurrent = ""
                        if prod['session'] == bank['current']:
                            iscurrent = "current"
                        print(" \t"+prod['release']+"\t"+','.join(prod['formats'])+"\t"+','.join(prod['types'])+"\t"+iscurrent)

                print('#' * 80)
                sys.exit(0)

        if options.show:
            if not options.bank:
                print("Bank option is required")
                sys.exit(1)

            bank = Bank(options.bank, no_log=False)
            for prod in bank.bank['production']:
                include = True
                if options.release and (prod['release'] != options.release and prod['prod_dir'] != options.release):
                    include =False
                if include:
                    session = bank.get_session_from_release(prod['release'])
                    print('#' * 80)
                    print("# Name:\t"+bank.bank['name'])
                    print("# Release:\t"+prod['release'])
                    formats = session['formats']
                    for fformat in list(formats.keys()):
                        print("# \tFormat:\t"+fformat)
                        for elt in formats[fformat]:
                            print("# \t\tTypes:\t"+','.join(elt['types']))
                            print("# \t\tTags:")
                            for tag in list(elt['tags'].keys()):
                                print("# \t\t\t"+tag+":"+elt['tags'][tag])
                            print("# \t\tFiles:")
                            for eltfile in elt['files']:
                                print("# \t\t\t"+eltfile)
            sys.exit(0)

        if options.check:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            bank = Bank(options.bank, no_log=False)
            print(options.bank+" check: "+str(bank.check())+"\n")
            sys.exit(0)


        if options.status:
            if options.bank:
                bank = Bank(options.bank, no_log=True)
                info = bank.get_bank_release_info(full=True)
                print(tabulate(info['info'], headers='firstrow', tablefmt='psql'))
                print(tabulate(info['prod'], headers='firstrow', tablefmt='psql'))
                # do we have some pending release(s)
                if 'pending' in info and len(info['pending']) > 1:
                    print(tabulate(info['pending'], headers='firstrow', tablefmt='psql'))
            else:
                banks = Bank.list()
                # Headers of output table
                banks_list = [["Name", "Type(s)", "Release", "Visibility"]]
                for bank in sorted(banks, key=lambda k: k['name']):
                    bank = Bank(bank['name'], no_log=True)
                    banks_list.append(bank.get_bank_release_info()['info'])
                print(tabulate(banks_list, headers="firstrow", tablefmt="psql"))
            sys.exit(0)

        if options.update:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            banks = options.bank.split(',')
            gres = True
            for bank in banks:
                options.bank = bank
                bmaj = Bank(bank, options)
                print('Log file: '+bmaj.config.log_file)
                res = bmaj.update(depends=True)
                if not res:
                    gres = False
                Notify.notifyBankAction(bmaj)
            if not gres:
                sys.exit(1)

        if options.freeze:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            if not options.release:
                print("Bank release is missing")
                sys.exit(1)
            bmaj = Bank(options.bank, options)
            res = bmaj.freeze(options.release)
            if not res:
                sys.exit(1)

        if options.unfreeze:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            if not options.release:
                print("Bank release is missing")
                sys.exit(1)
            bmaj = Bank(options.bank, options)
            res = bmaj.unfreeze(options.release)
            if not res:
                sys.exit(1)

        if options.remove or options.removeall:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            if options.remove and not options.release:
                print("Bank release is missing")
                sys.exit(1)
            if options.removeall:
                bmaj = Bank(options.bank, options, no_log=True)
                print('Log file: '+bmaj.config.log_file)
                res = bmaj.removeAll(options.force)
            else:
                bmaj = Bank(options.bank, options)
                print('Log file: '+bmaj.config.log_file)
                res = bmaj.remove(options.release)
                Notify.notifyBankAction(bmaj)
            if not res:
                sys.exit(1)

        if options.removepending:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            bmaj = Bank(options.bank, options, no_log=True)
            print('Log file: '+bmaj.config.log_file)
            res = bmaj.remove_pending(options.release)
            if not res:
                sys.exit(1)

        if options.unpublish:
            if not options.bank:
                print("Bank name is missing")
                sys.exit(1)
            bmaj = Bank(options.bank, options)
            bmaj.load_session()
            bmaj.unpublish()
            sys.exit(0)

        if options.publish:
            if not options.bank:
                print("Bank name or release is missing")
                sys.exit(1)
            bmaj = Bank(options.bank, options)
            print('Log file: '+bmaj.config.log_file)
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
                print("No production session could be found for this release")
                sys.exit(1)
            bmaj.session._session = session
            bmaj.publish()
    except Exception as e:
        print(str(e))

if __name__ == '__main__':
    main()
