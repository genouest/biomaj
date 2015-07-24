from builtins import range
from builtins import object
import threading
import logging
from biomaj.process.metaprocess import MetaProcess

class ProcessFactory(object):
    '''
    Manage process execution
    '''

    NB_THREAD = 2

    def __init__(self, bank):
        self.bank = bank
        self.threads_tasks = []
        if self.bank.session:
            self.meta_data = self.bank.session.get('per_process_metadata')
        else:
            self.meta_data = {}

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
        running_th = []
        for thread_tasks in self.threads_tasks:
            meta_thread = MetaProcess(self.bank, thread_tasks, self.meta_status, self.meta_data, simulate)
            meta_thread._lock = ProcessFactory._LOCK
            meta_thread.workflow = self.workflow
            meta_thread.start()
            threads.append(meta_thread)
            running_th.append(meta_thread)
        # Wait for the end of the threads
        kill_received = False
        while len(running_th) > 0:
            try:
                # Join all threads using a timeout so it doesn't block
                # Filter out threads which have been joined or are None
                running_th = [t.join(1000) for t in running_th if t is not None and t.isAlive()]
            except KeyboardInterrupt:
                logging.warn("Ctrl-c received! Sending kill to threads...")
                logging.warn("Running tasks will continue and process will stop.")
                kill_received = True
                for t in running_th:
                    t.kill_received = True

        for meta_thread in threads:
            meta_thread.join()
        global_meta_status = {}
        global_status = True

        for meta_thread in threads:
            for meta in meta_thread.meta_status:
                global_meta_status[meta] = meta_thread.meta_status[meta]
            if not meta_thread.global_status:
                global_status = False

        if kill_received:
            global_status = False

        logging.debug('Meta threads are over')
        return (global_status, global_meta_status)

    def fill_tasks_in_threads(self, metas):
        '''
        Dispatch meta processes in available threads
        '''
        self.threads_tasks = []
        for i in range(0, ProcessFactory.NB_THREAD):
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
        self.workflow = 'preprocess'

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
        self.workflow = 'removeprocess'


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
        self.workflow = 'postprocess'

    def run(self, simulate=False):
        '''
        Run processes

        :param simulate: does not execute process
        :type simulate: bool
        :return: status of execution - bool
        '''
        logging.info('PROC:POST:BLOCK')
        blocks = self.bank.config.get('BLOCKS')
        if blocks is None or blocks == '':
            process_blocks = []
        else:
            process_blocks = blocks.split(',')
        metas = []
        self.meta_status = None
        global_status = True
        for process_block in process_blocks:
            if not global_status:
                continue
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


ProcessFactory._LOCK = threading.Lock()
