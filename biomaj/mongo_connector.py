from pymongo import MongoClient


class MongoConnector:
    """
    Connector to mongodb
    """

    client = None
    db = None
    banks = None
    users = None

    def __init__(self, url, db):
        MongoConnector.client = MongoClient(url)
        MongoConnector.db = MongoConnector.client[db]
        MongoConnector.banks = MongoConnector.db.banks
        MongoConnector.users = MongoConnector.db.users
        MongoConnector.db_schema = MongoConnector.db.db_schema
        MongoConnector.history = MongoConnector.db.history
