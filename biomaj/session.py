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

  def __init__(self, config, config_bank):
    self.config = config
    self.config_bank = config_bank
    self._session = { 'id':  time.time(), 'status': {}, 'files': [] }
    for flow in Workflow.FLOW:
        self._session['status'][flow['name']] = False

  def load(self, session):
    '''
    Load an existing session
    '''
    self._session = session

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
