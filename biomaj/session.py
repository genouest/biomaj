import os
import ConfigParser
import logging
import time
import copy

from biomaj.workflow import Workflow, UpdateWorkflow, RemoveWorkflow


class Session:
  '''
  BioMAJ bank session
  '''

  OVER = 0

  def __init__(self, name, config, flow=Workflow.FLOW, action='update'):
    '''
    Creates a new session

    :param name: Name of the bank
    :type name: str
    :param config: bank and global config
    :type config: BiomajConfig
    :param flow: Workflow tasks
    :param action: type of flow update|remove
    :type action: str
    :type flow: dict
    '''
    self.name = name
    self.config = config
    self.flow = copy.deepcopy(flow)
    self._session = { 'id':  time.time(),
                      'status': {},
                      'files': [],
                      'release': 'none',
                      'process': {
                                  'post': {},
                                  'pre': {},
                                  'remove': {}
                                  }
                    }
    for flow in self.flow:
        self._session['status'][flow['name']] = False

    self.set('last_modified',self.config.last_modified)

    # Default is update
    self._session['action'] = action

  def reset_proc(self, type_proc, proc=None):
    '''
    Reset status of processes for type in session

    :param type_proc: post pre or remove
    :type type_proc: Workflow.POSTPROCESS, Workflow.PREPROCESS, Workflow.REMOVEPROCESS
    :param proc: reset from block/meta/proc, all reset all
    :type proc: str
    '''
    if type_proc == Workflow.FLOW_POSTPROCESS:
      if proc in self._session['process']['post']:
        self.reset_meta(self._session['process']['post'][proc])
      else:
        for elt in self._session['process']['post'].keys():
          self.reset_meta(self._session['process']['post'][elt], proc)
    elif type_proc == Workflow.FLOW_PREPROCESS:
      self.reset_meta(self._session['process']['pre'])
    elif type_proc == Workflow.FLOW_REMOVEPROCESS:
      self.reset_meta(self._session['process']['remove'], proc)

  def reset_meta(self, metas, proc=None):
    '''
    Reset status of meta processes
    '''
    if proc in metas:
      self.reset_process(procs)
    else:
      for meta in metas.keys():
        self.reset_process(metas[meta], proc)

  def reset_process(self, processes, proc=None):
    '''
    Reset status of processes
    '''
    set_to_false = False
    for process in processes.keys():
      if process == proc or proc is None:
        set_to_false = True
      if set_to_false:
        processes[process] = False


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
    if attr in self._session:
      return self._session[attr]
    else:
      return None

  def set(self, attr, value):
    '''
    Sets an attribute of session
    '''
    self._session[attr] = value

  def get_status(self, status):
    '''
    Return status for a flow event
    '''
    return self._session['status'][status]

  def set_status(self, status, value):
    '''
    Set status for a flow event
    '''
    self._session['status'][status] = value
