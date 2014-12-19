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
      MongoConnector(BiomajConfig.global_config.get('GENERAL','db.url'),
                      BiomajConfig.global_config.get('GENERAL','db.name'))

    self.users = MongoConnector.users
    self.id = user
    self.user = self.users.find_one({'id': user})
    con = None
    if not self.user and BiomajConfig.global_config.get('GENERAL','use_ldap') == '1':
      # Check if in ldap
      import ldap
      try:
          ldap_host = BiomajConfig.global_config.get('GENERAL','ldap.host')
          ldap_port = BiomajConfig.global_config.get('GENERAL','ldap.port')
          con = ldap.initialize('ldap://' + ldap_host + ':' + str(ldap_port))
      except Exception, err:
              logging.error(str(err))
              self.user = None
      ldap_dn = BiomajConfig.global_config.get('GENERAL','ldap.dn')
      base_dn = 'ou=People,' + ldap_dn
      filter = "(&""(|(uid=" + user + ")(mail=" + user + ")))"
      try:
          con.simple_bind_s()
          attrs = ['mail']
          results = con.search_s(base_dn, ldap.SCOPE_SUBTREE, filter, attrs)
          if results:
            ldapMail = None
            for dn, entry in results:
              user_dn = str(dn)
              ldapMail = entry['mail'][0]
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
      import ldap
      con = None
      try:
          ldap_host = BiomajConfig.global_config.get('GENERAL','ldap.host')
          ldap_port = BiomajConfig.global_config.get('GENERAL','ldap.port')
          con = ldap.initialize('ldap://' + ldap_host + ':' + str(ldap_port))
      except Exception, err:
              logging.error(str(err))
              return False
      ldap_dn = BiomajConfig.global_config.get('GENERAL','ldap.dn')
      base_dn = 'ou=People,' + ldap_dn
      filter = "(&(|(uid=" + self.user['id'] + ")(mail=" + self.user['id'] + ")))"
      try:
          con.simple_bind_s()
      except Exception as err:
        logging.error(str(err))
        return False
      try:
        attrs = ['mail']
        results = con.search_s(base_dn, ldap.SCOPE_SUBTREE, filter, attrs)
        user_dn = None
        ldapMail = None
        ldapHomeDirectory = None
        for dn, entry in results:
            user_dn = str(dn)
            ldapMail = entry['mail'][0]
        con.simple_bind_s(user_dn, password)
        con.unbind_s()
        if user_dn:
          return True
      except Exception, err:
        logging.error('Bind error: '+str(err))

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
