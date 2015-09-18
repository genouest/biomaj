from builtins import str
from builtins import range
#import os
import logging
#import datetime
#import time
#import re
import threading
import copy
#import tarfile
#import zipfile
import traceback

class DownloadThread(threading.Thread):

    NB_THREAD = 2


    @staticmethod
    def get_threads(downloader, local_dir):
        '''
        Creates a list of thread for download

        :param downloader: downloader to use
        :type downloader: :class:`biomaj.download.interface.DownloadInterface`
        :param local_dir: directory where files should be downloaded
        :type local_dir: str
        :return: list of threads
        '''
        threads = []
        # Creates threads with copies of the downloader
        for i in range(0, DownloadThread.NB_THREAD):
            new_download = copy.deepcopy(downloader)
            new_download.files_to_download = []
            th = DownloadThread(new_download, local_dir)
            threads.append(th)
        # Now dispatch the files to download to the threads
        thread_id = 0
        for dfile in downloader.files_to_download:
            if thread_id == DownloadThread.NB_THREAD:
                thread_id = 0
            threads[thread_id].downloader.files_to_download.append(dfile)
            thread_id += 1
        return threads

    @staticmethod
    def get_threads_multi(downloaders, local_dir):
        '''
        Dispatch multiple downloaders on threads

        :param downloaders: downlaoders to dispatch in threads
        :type downloaders: list of :class:`biomaj.download.interface.DownloadInterface`
        :param local_dir: directory where files should be downloaded
        :type local_dir: str
        :return: list of threads
        '''
        threads = []
        # Creates threads with copies of the downloader
        thread_id = 0
        for downloader in downloaders:
            if thread_id == DownloadThread.NB_THREAD:
                thread_id = 0
            th = DownloadThread(downloader, local_dir)
            threads.append(th)
            thread_id += 1
        return threads

    def __init__(self, downloader, local_dir):
        '''
        Download thread to download a list of files

        :param downloader: downloader to use
        :type downloader: :class:`biomaj.download.interface.DownloadInterface`
        :param local_dir: directory to download files
        :type local_dir: str
        '''
        threading.Thread.__init__(self)
        self.downloader = downloader
        self.downloader.mkdir_lock = DownloadThread.MKDIR_LOCK
        self.downloader.kill_received = False
        self.local_dir = local_dir
        self.error = False
        self._stopevent = threading.Event()

    def run(self):
        logging.info('Start download thread')
        if self.downloader is None:
            return True
        self.error = False
        try:
            self.downloader.download(self.local_dir)
            self.downloader.close()
        except Exception as e:
            logging.error('Error in download execution of thread: '+str(e))
            logging.debug(traceback.format_exc())
            self.error = True

    def stop(self):
        self._stopevent.set()


DownloadThread.MKDIR_LOCK = threading.Lock()
