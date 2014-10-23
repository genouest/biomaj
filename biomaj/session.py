import os
import ConfigParser
import logging
import time
import copy

from biomaj.workflow import Workflow


class Session:
  '''
  BioMAJ bank session
  '''

  OVER = 0

  def __init__(self, name, config):
    '''
    Creates a new session

    :param name: Name of the bank
    :type name: str
    :param config: bank and global config
    :type config: BiomajConfig
    '''
    self.name = name
    self.config = config
    self._session = { 'id':  time.time(), 'status': {}, 'files': [], 'release': 'none' }
    for flow in Workflow.FLOW:
        self._session['status'][flow['name']] = False

  def load(self, session):
    '''
    Load an existing session
    '''
    self._session = session

  def get_release_directory(self):
    return self.name+'-'+self._session['release']

  def get(self, attr):
    '''
    Return an attribute of session
    '''
    return self._session[attr]

  def get_status(self, status):
    '''
    Return status for a flow event
    '''
    return self._session['status'][status]
