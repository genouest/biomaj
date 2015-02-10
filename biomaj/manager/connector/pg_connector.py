'''
Created on Feb 10, 2015

@author: tuco
'''
from biomaj.biomaj.manager.connector import Connector
import psycopg2

class PgConnector(Connector):

    def __init__(self, type=None):
        