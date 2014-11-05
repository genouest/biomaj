import os
import logging
import datetime
import time
import re
import threading
import copy
import tarfile
import zipfile

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
    for i in range(0,DownloadThread.NB_THREAD):
      new_download = copy.deepcopy(downloader)
      new_download.files_to_download = []
      th = DownloadThread(new_download, local_dir)
      threads.append(th)
    # Now dispatch the files to download to the threads
    thread_id = 0
    for file in downloader.files_to_download:
      if thread_id == DownloadThread.NB_THREAD:
        thread_id = 0
      threads[thread_id].downloader.files_to_download.append(file)
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
    self.local_dir = local_dir
    self.error = False
    self._stopevent = threading.Event( )

  def run(self):
    logging.info('Start download thread')
    self.error = False
    try:
      self.downloader.download(self.local_dir)
      self.downloader.close()
    except Exception as e:
      logging.error('Error in download execution of thread: '+str(e))
      logging.debug(traceback.format_exc())
      self.error = True
