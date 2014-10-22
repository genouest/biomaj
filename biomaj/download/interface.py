import os
import logging
import datetime
import time

class DownloadInterface:

  files_num_threads = 4

  def __init__(self):
    self.files_to_download = []

  @staticmethod
  def month_to_num(date):
    return{
          'Jan' : 1,
          'Feb' : 2,
          'Mar' : 3,
          'Apr' : 4,
          'May' : 5,
          'Jun' : 6,
          'Jul' : 7,
          'Aug' : 8,
          'Sep' : 9,
          'Oct' : 10,
          'Nov' : 11,
          'Dec' : 12
          }[date]



  def set_permissions(self, file_path, file_info):
    '''
    Sets file attributes to remote ones
    '''
    logging.warn(file_info)
    month = DownloadInterface.month_to_num(file_info['month'])
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
    '''
    pass

  def list(self):
    '''
    List directory
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
