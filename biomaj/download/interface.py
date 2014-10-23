import os
import logging
import datetime
import time
import re

import tarfile
import zipfile

from biomaj.utils import Utils

class DownloadInterface:
  '''
  Main interface that all downloaders must extend
  '''

  files_num_threads = 4

  def __init__(self):
    self.files_to_download = []
    self.files_to_copy = []



  def set_permissions(self, file_path, file_info):
    '''
    Sets file attributes to remote ones
    '''
    ftime = datetime.date(int(file_info['year']),int(file_info['month']),int(file_info['day']))
    settime = time.mktime(ftime.timetuple())
    os.utime(file_path, (settime, settime))

  def download_or_copy(self, available_files, root_dir):
    '''
    If a file to download is available in available_files, copy it instead of downloading it.

    Update the instance variables files_to_download and files_to_copy

    :param available_files: list of files available in root_dir
    :type available files: list
    :param root_dir: directory where files are available
    :type root_dir: str
    '''
    self.files_to_copy = []
    available_files.sort(key=lambda x: x['name'])
    self.files_to_download.sort(key=lambda x: x['name'])

    new_files_to_download = []

    test1_tuples = ((d['name'], d['year'], d['month'], d['day'], d['size']) for d in self.files_to_download)
    test2_tuples = set((d['name'], d['year'], d['month'], d['day'], d['size']) for d in available_files)
    new_or_modified_files = [t for t in test1_tuples if t not in test2_tuples]
    index = 0
    if len(new_or_modified_files) > 0:
      for file in self.files_to_download:
        if index < len(new_or_modified_files) and \
          file['name'] == new_or_modified_files[index][0]:
          new_files_to_download.append(file)
          index += 1
        else:
          file['root'] = root_dir
          self.files_to_copy.append(file)

    else:
      # Copy everything
      for file in self.files_to_download:
        file['root'] = root_dir
        self.files_to_copy.apppend(file)

    self.files_to_download = new_files_to_download


  def match(self, patterns = []):
    '''
    Find files matching patterns
    '''
    pass


  def download(self, local_dir):
    '''
    Download remote files to local_dir

    :param local_dir: Directory where files should be downloaded
    :type local_dir: str
    :return: list of downloaded files
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
