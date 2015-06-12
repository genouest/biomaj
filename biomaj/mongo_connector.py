from builtins import object
from pymongo import MongoClient


class MongoConnector(object):
    '''
    Connector to mongodb
    '''

    client = None
    db = None
    banks = None
    users = None

    def __init__(self, url, db):
        MongoConnector.client = MongoClient(url)
        MongoConnector.db = MongoConnector.client[db]
        MongoConnector.banks = MongoConnector.db.banks
        MongoConnector.users = MongoConnector.db.users
