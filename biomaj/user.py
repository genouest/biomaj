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

  def check_password(self, password):
    if self.user is None:
      return False
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
                      'email': email
                    }
        self.user['_id'] = self.users.insert(self.user)
