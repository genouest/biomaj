from biomaj.mongo_connector import MongoConnector
from biomaj.manager.bankrelease import BankRelease

class NoSQLConnector(MongoConnector):

    url = None
    driver = None

    def get_bank_list(self):
        """
        Get the list of bank available from the database
        :return: List of bank name
        :rtype: List of string
        """
        self._is_connected()
        banks = MongoConnector.banks.find({}, {'name': 1, '_id': 0})
        list = []
        for bank in banks:
            list.append(bank['name'])
            print "[mongo] %s" % bank['name']
        return list

    def _history(self, bank=None, to_json=False):
        '''
            Get the release history of a specific bank

            :param name: Name of the bank
            :type name: String
            :param idbank: Bank id (primary key)
            :type idbank: Integer
            :param to_json: Converts output to json
            :type name: Boolean (Default False)
            :return: A dict with 2 keys: 'available' & 'deleted' production/session
        '''
        if not bank:
            raise Exception("Bank instance is required")
        prodsids = []
        history = {'available': [], 'deleted': []}
        # We get the status of the last action
        action = MongoConnector.banks.find({'name': bank.name}, {'_id': 0, 'status': 1})
        productions = MongoConnector.banks.find({'name': bank.name}, {'_id': 0, 'production': 1})
        sessions = MongoConnector.banks.find({'name': bank.name },
                                             {'_id': 0, 'name': 1, 'sessions.update': 1,
                                              'sessions.release': 1, 'sessions.id': 1, 'sessions.remoterelease': 1,
                                              'sessions.remove': 1, 'sessions.update': 1, 'sessions.last_update_time': 1,
                                              'sessions.last_modified': 1, 'sessions.status': 1, 'sessions.action': 1})
        for p in productions:
            for i in p['production']:
                prodsids.append(i['session'])

        for session in sessions:
            for sess in session['sessions']:
            #if 'status' in match['status']['publish']:
            #    continue
            # online (available) versions are stored in the production
            # others (deleted) are the one in session which are not in produciotn
                if sess['id'] in prodsids:
                    history['available'].append(sess)
                else:
                    history['deleted'].append(sess)
        print "Available release(s): %d (%s)" % (len(history['available']), ','.join(map(lambda(d): d['remoterelease'], history['available'])))
        print "Deleted release(s)  : %d (%s)" % (len(history['deleted']), ','.join(map(lambda(d): d['remoterelease'], history['deleted'])))
        return history

    def _is_connected(self):
        """
          Check the bank object has a connection to the database set.
          :return: raise Exception if no connection set
        """
        if MongoConnector.db:
            return True
        else:
            raise Exception("No db connection available. Build object with 'connect=True' to access database.")

    def _check_bank(self, name=None):
        """
            Checks a bank exists in the database
            :param name: Name of the bank to check [Default self.name]
            :param name: String
            :return:
            :throws: Exception if bank does not exists
        """
        self._is_connected()
        if name is None:
            raise Exception("Can't check bank, name not set")
        res = MongoConnector.banks.find({'name': name}, {'_id': 1})
        if res.count() > 1:
            raise Exception("More than one bank %s found!" % name)
        elif res.count() == 0:
            raise Exception("Bank %s does not exists" % name)
        return res[0]['_id']


    def _get_releases(self, bank):
        """

        :param bank: Bank instance
        :return: List of BankRelease
        """
        print "Getting releases for bank {0}".format(bank.name)
        sessions = MongoConnector.banks.find({"name": bank.name}, {"sessions": 1, "status": 1, "_id": 0})
        status = MongoConnector.banks.find({"name": bank.name}, {"status": 1, "_id": 0})
        stsess = status[0]['status']['session']
        sessions = sessions[0]['sessions']
        releases = []
        for session in sessions:
            rel = BankRelease()
            if session['id'] == stsess:
                rel.status = 'current'
            print session



    def _current_release(self):
        """
        Get the last 'current' release of a bank
        :return: list
        """
        pass