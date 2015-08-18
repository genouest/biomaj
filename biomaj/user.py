from builtins import str
from builtins import object
import bcrypt
import logging

from biomaj.mongo_connector import MongoConnector
from biomaj.config import BiomajConfig

class BmajUser(object):
    '''
    Biomaj User
    '''

    def __init__(self, user):

        if MongoConnector.db is None:
            MongoConnector(BiomajConfig.global_config.get('GENERAL', 'db.url'),
                            BiomajConfig.global_config.get('GENERAL', 'db.name'))

        self.users = MongoConnector.users
        self.id = user
        self.user = self.users.find_one({'id': user})
        ldap_server = None
        con = None
        if not self.user and BiomajConfig.global_config.get('GENERAL', 'use_ldap') == '1':
            # Check if in ldap
            #import ldap
            from ldap3 import Server, Connection, AUTH_SIMPLE, STRATEGY_SYNC, STRATEGY_ASYNC_THREADED, SEARCH_SCOPE_WHOLE_SUBTREE, GET_ALL_INFO
            try:
                ldap_host = BiomajConfig.global_config.get('GENERAL', 'ldap.host')
                ldap_port = BiomajConfig.global_config.get('GENERAL', 'ldap.port')
                #con = ldap.initialize('ldap://' + ldap_host + ':' + str(ldap_port))
                ldap_server = Server(ldap_host, port=int(ldap_port), get_info=GET_ALL_INFO)
                con = Connection(ldap_server, auto_bind=True, client_strategy=STRATEGY_SYNC, check_names=True)
            except Exception as err:
                logging.error(str(err))
                self.user = None
            ldap_dn = BiomajConfig.global_config.get('GENERAL', 'ldap.dn')
            base_dn = 'ou=People,' + ldap_dn
            ldapfilter = "(&(|(uid=" + user + ")(mail=" + user + ")))"
            try:
                #con.simple_bind_s()
                attrs = ['mail']
                #results = con.search_s(base_dn, ldap.SCOPE_SUBTREE, filter, attrs)
                con.search(base_dn, ldapfilter, SEARCH_SCOPE_WHOLE_SUBTREE, attributes=attrs)
                if con.response:
                    ldapMail = None
                    #for dn, entry in results:
                    for r in con.response:
                        user_dn = str(r['dn'])
                        #if 'mail' not in entry:
                        if 'mail' not in r['attributes']:
                            logging.error('Mail not set for user '+user)
                        else:
                            #ldapMail = entry['mail'][0]
                            ldapMail = r['attributes']['mail'][0]
                    self.user = {
                                  'id' : user,
                                  'email': ldapMail,
                                  'is_ldap': True
                                }
                    self.user['_id'] = self.users.insert(self.user)

                else:
                    self.user = None
            except Exception as err:
                logging.error(str(err))
            if con:
                con.unbind()

    @staticmethod
    def user_remove(user_name):
        '''
        Remove a user from db

        :param user_name: user name
        :type user_name: str
        '''
        MongoConnector.users.remove({'id': user_name})

    @staticmethod
    def user_banks(user_name):
        '''
        Get user banks name

        :param user_name: user identifier
        :type user_name: str
        :return: list of bank name
        '''
        banks = MongoConnector.banks.find({'properties.owner': user_name}, {'name':1})
        return banks

    @staticmethod
    def list():
        '''
        Get users
        '''
        return MongoConnector.users.find()

    def check_password(self, password):
        if self.user is None:
            return False

        if self.user['is_ldap']:
            #import ldap
            con = None
            ldap_server = None
            #try:
            #    ldap_host = BiomajConfig.global_config.get('GENERAL','ldap.host')
            #    ldap_port = BiomajConfig.global_config.get('GENERAL','ldap.port')
            #    con = ldap.initialize('ldap://' + ldap_host + ':' + str(ldap_port))
            from ldap3 import Server, Connection, AUTH_SIMPLE, STRATEGY_SYNC, STRATEGY_ASYNC_THREADED, SEARCH_SCOPE_WHOLE_SUBTREE, GET_ALL_INFO
            from ldap3.core.exceptions import LDAPBindError
            try:
                ldap_host = BiomajConfig.global_config.get('GENERAL', 'ldap.host')
                ldap_port = BiomajConfig.global_config.get('GENERAL', 'ldap.port')
                #con = ldap.initialize('ldap://' + ldap_host + ':' + str(ldap_port))
                ldap_server = Server(ldap_host, port=int(ldap_port), get_info=GET_ALL_INFO)
                con = Connection(ldap_server, auto_bind=True, client_strategy=STRATEGY_SYNC, check_names=True)
            except Exception as err:
                logging.error(str(err))
                return False
            ldap_dn = BiomajConfig.global_config.get('GENERAL','ldap.dn')
            base_dn = 'ou=People,' + ldap_dn
            ldapfilter = "(&(|(uid=" + self.user['id'] + ")(mail=" + self.user['id'] + ")))"
            #try:
            #    con.simple_bind_s()
            #except Exception as err:
            #    logging.error(str(err))
            #    return False
            try:
                attrs = ['mail']
                con.search(base_dn, ldapfilter, SEARCH_SCOPE_WHOLE_SUBTREE, attributes=attrs)
                #results = con.search_s(base_dn, ldap.SCOPE_SUBTREE, filter, attrs)
                user_dn = None
                ldapMail = None
                ldapHomeDirectory = None
                for r in con.response:
                    user_dn = str(r['dn'])
                    ldapMail = r['attributes']['mail'][0]
                #for dn, entry in results:
                #    user_dn = str(dn)
                #    ldapMail = entry['mail'][0]
                con.unbind()
                con = Connection(ldap_server, auto_bind=True, read_only=True, client_strategy=STRATEGY_SYNC, user=user_dn, password=password, authentication=AUTH_SIMPLE, check_names=True)
                con.unbind()
                #con.simple_bind_s(user_dn, password)
                #con.unbind_s()
                if user_dn:
                    return True
            except LDAPBindError as err:
                logging.error('Bind error: '+str(err))
                return False
            except Exception as err:
                logging.error('Bind error: '+str(err))
                return False

        else:
            hashed = bcrypt.hashpw(password, self.user['hashed_password'])
            if hashed == self.user['hashed_password']:
                return True
            else:
                return False

    def remove(self):
        if self.user is None:
            return False
        self.users.remove({'_id': self.user['_id']})
        return True

    def create(self, password, email=''):
        '''
        Create a new user
        '''
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        if self.user is None:
            self.user = {
                          'id' : self.id,
                          'hashed_password': hashed,
                          'email': email,
                          'is_ldap': False
                        }
            self.user['_id'] = self.users.insert(self.user)
