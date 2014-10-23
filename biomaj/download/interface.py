import os
import logging
import datetime
import time
import re

import tarfile
import zipfile

from biomaj.utils import Utils

class DownloadInterface:

  files_num_threads = 4

  def __init__(self):
    self.files_to_download = []



  def set_permissions(self, file_path, file_info):
    '''
    Sets file attributes to remote ones
    '''
    logging.warn(file_info)
    month = Utils.month_to_num(file_info['month'])
    ftime = datetime.date(int(file_info['yearortime']),month,int(file_info['day']))
    settime = time.mktime(ftime.timetuple())
    os.utime(file_path, (settime, settime))

  def match(self, patterns = []):
    '''
    Find files matching patterns
    '''
    pass


  def download(self, local_dir):
    '''
    Download remote files to local_dir

    :return: list of files to download
    '''
    pass

  def list(self):
    '''
    List directory

    :return: tuple of file list and dir list
    '''
    pass

  def chroot(self, cwd):
    '''
    Change directory
    '''
    pass

  def close(self):
    '''
    Close connection
    '''
    pass
