import threading
import logging
from biomaj.process.metaprocess import MetaProcess

class ProcessFactory:
  '''
  Manage process execution
  '''

  NB_THREAD = 2

  def __init__(self, bank):
    self.bank = bank
    self.threads_tasks = []

  def run(self, simulate=False):
    '''
    Run processes

    :param simulate: does not execute process
    :type simulate: bool
    :return: status of execution - bool
    '''
    pass

  def run_threads(self, simulate=False):
    '''
    Start meta threads

    :param simulate: do not execute processes
    :type simulate: bool
    :return: tuple global execution status and status per meta process
    '''
    logging.debug('Start meta threads')
    threads = []
    for thread_tasks in self.threads_tasks:
      meta_thread = MetaProcess(self.bank, thread_tasks, self.meta_status, simulate)
      meta_thread.start()
      threads.append(meta_thread)
    # Wait for the end of the threads
    for meta_thread in threads:
      meta_thread.join()
    global_meta_status = {}
    global_status = True

    for meta_thread in threads:
      if self.bank.session:
        for meta_data in meta_thread.meta_data.keys():
          session_formats = self.bank.session.get('formats')
          if meta_data not in session_formats:
            #session_formats[meta_data] = [meta_thread.meta_data[meta_data]]
            session_formats[meta_data] = meta_thread.meta_data[meta_data]
          else:
            #session_formats[meta_data].append(meta_thread.meta_data[meta_data])
            session_formats[meta_data] += meta_thread.meta_data[meta_data]

      for meta in meta_thread.meta_status:
        global_meta_status[meta] = meta_thread.meta_status[meta]
      if not meta_thread.global_status:
        global_status = False

    logging.debug('Meta threads are over')
    return (global_status, global_meta_status)

  def fill_tasks_in_threads(self, metas):
    '''
    Dispatch meta processes in available threads
    '''
    self.threads_tasks = []
    for i in range(0,ProcessFactory.NB_THREAD):
      # Fill array of meta process in future threads
      self.threads_tasks.append([])
    thread_id = 0
    for meta in metas:
      meta_process = meta.strip()
      if thread_id == ProcessFactory.NB_THREAD:
        thread_id = 0
      self.threads_tasks[thread_id].append(meta_process)
      thread_id += 1


class PreProcessFactory(ProcessFactory):
  '''
  Manage preprocesses
  '''

  def __init__(self, bank, metas=None):
    '''
    Creates a preprocess factory

    :param bank: Bank
    :type bank: :class:`biomaj.bank.Bank`
    :param metas: initial status of meta processes
    :type metas: dict
    '''
    ProcessFactory.__init__(self, bank)
    self.meta_status = None
    if metas is not None:
      self.meta_status = metas

  def run(self, simulate=False):
    '''
    Run processes

    :param simulate: does not execute process
    :type simulate: bool
    :return: status of execution - bool
    '''
    logging.info('PROC:PRE')
    if self.bank.config.get('db.pre.process') is None:
      metas = []
    else:
      metas = self.bank.config.get('db.pre.process').split(',')
    self.fill_tasks_in_threads(metas)
    (status, self.meta_status) = self.run_threads(simulate)
    return status

class RemoveProcessFactory(ProcessFactory):
  '''
  Manage remove processes
  '''

  def __init__(self, bank, metas=None):
    '''
    Creates a remove process factory

    :param bank: Bank
    :type bank: :class:`biomaj.bank.Bank`
    :param metas: initial status of meta processes
    :type metas: dict
    '''
    ProcessFactory.__init__(self, bank)
    self.meta_status = None
    if metas is not None:
      self.meta_status = metas


  def run(self, simulate=False):
    '''
    Run processes

    :param simulate: does not execute process
    :type simulate: bool
    :return: status of execution - bool
    '''
    logging.info('PROC:REMOVE')
    if self.bank.config.get('db.remove.process') is None:
      metas = []
    else:
      metas = self.bank.config.get('db.remove.process').split(',')
    self.fill_tasks_in_threads(metas)
    (status, self.meta_status) = self.run_threads(simulate)
    return status

class PostProcessFactory(ProcessFactory):
  '''
  Manage postprocesses

  self.blocks: dict of meta processes status
  Each meta process status is a dict of process status
  '''

  def __init__(self, bank, blocks=None):
    '''
    Creates a postprocess factory

    :param bank: Bank
    :type bank: :class:`biomaj.bank.Bank`
    :param blocks: initial status of block processes
    :type blocks: dict
    '''
    ProcessFactory.__init__(self, bank)
    self.blocks = {}
    if blocks is not None:
      self.blocks = blocks

  def run(self, simulate=False):
    '''
    Run processes

    :param simulate: does not execute process
    :type simulate: bool
    :return: status of execution - bool
    '''
    logging.info('PROC:POST:BLOCK')
    blocks = self.bank.config.get('BLOCKS')
    if blocks is None:
      process_blocks = []
    else:
      process_blocks = blocks.split(',')
    metas = []
    self.meta_status = None
    global_status = True
    for process_block in process_blocks:
      logging.info('PROC:POST:BLOCK:'+process_block)
      if process_block in self.blocks:
        self.meta_status = self.blocks[process_block]
      # run each block
      metas = self.bank.config.get(process_block.strip()+'.db.post.process').split(',')
      self.fill_tasks_in_threads(metas)
      (status, self.blocks[process_block]) = self.run_threads(simulate)
      if not status:
        global_status = False
    return global_status
