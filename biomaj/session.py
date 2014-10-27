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

  def __init__(self, name, config, flow=Workflow.FLOW):
    '''
    Creates a new session

    :param name: Name of the bank
    :type name: str
    :param config: bank and global config
    :type config: BiomajConfig
    :param flow: Workflow tasks
    :type flow: dict
    '''
    self.name = name
    self.config = config
    self.flow = flow
    self._session = { 'id':  time.time(), 'status': {}, 'files': [], 'release': 'none' }
    for flow in self.flow:
        self._session['status'][flow['name']] = False

  def load(self, session):
    '''
    Load an existing session
    '''
    self._session = session

  def get_release_directory(self):
    '''
    Get release directroy name
    '''
    return self.name+'-'+self._session['release']

  def get_full_release_directory(self):
    '''
    Get bank directroy for this release
    '''
    release_dir = os.path.join(self.config.get('data.dir'),
                  self.config.get('dir.version'),
                  self.get_release_directory())
    return release_dir

  def get_offline_directory(self):
    '''
    Get bank offline directory
    '''
    return os.path.join(self.config.get('data.dir'),self.config.get('offline.dir.name'))

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
