import datetime
import logging
import pycurl
import StringIO
import os
import re
import urllib

from biomaj.download.interface import DownloadInterface
from biomaj.download.ftp import FTPDownload
from biomaj.utils import Utils

class MultiDownload(DownloadInterface):
  '''
  Base interface for a downloader using multiple downloaders
  '''
  def __init__(self):
    DownloadInterface.__init__(self)
    self.downloaders = []
    self.files_to_download = []

  def add_downloaders(self, downloaders):
    '''
    Adds a list of downloaders
    '''
    self.downloaders += downloaders
    for d in downloaders:
      self.files_to_download += d.files_to_download


  def match(self, patterns, file_list, dir_list=[], prefix=''):
    self.files_to_download = []
    for d in self.downloaders:
      d.match(patterns, d.files_to_download, [], prefix)
    self.files_to_download = []
    for d in self.downloaders:
      self.files_to_download += d.files_to_download

  def download(self, local_dir):
    self.files_to_download = []
    for d in self.downloaders:
      d.download(local_dir)
    self.files_to_download = []
    for d in self.downloaders:
      self.files_to_download += d.files_to_download
    return (self.files_to_download, [])

  def list(self):
    self.files_to_download = []
    for d in self.downloaders:
      d.list()
    self.files_to_download = []
    for d in self.downloaders:
      self.files_to_download += d.files_to_download
    return (self.files_to_download, [])

  def close(self):
    for d in self.downloaders:
      d.close()


class DirectFTPDownload(FTPDownload):
  '''
  download a list of files from FTP, no regexp
  '''

  def __init__(self, protocol, host, rootdir='', file_list=[]):
    '''

    Initialize the files in list with today as last-modification date.
    Size is also preset to zero, size will be set after download

    :param file_list: list of files to download on server
    :type file_list: list
    '''
    FTPDownload.__init__(self, protocol, host, rootdir)
    today = datetime.date.today()
    self.files_to_download = []
    for file in file_list:
      rfile = {}
      rfile['root'] = self.rootdir
      rfile['permissions'] = ''
      rfile['group'] = ''
      rfile['user'] = ''
      rfile['size'] = 0
      rfile['month'] = today.month
      rfile['day'] = today.day
      rfile['year'] = today.year
      rfile['name'] = file
      self.files_to_download.append(rfile)

  def list(self, directory=''):
    '''
    FTP protocol does not give us the possibility to get file date from remote url
    '''
    return (self.files_to_download,[])

  def match(self, patterns, file_list, dir_list=[], prefix=''):
    '''
    All files to download match, no pattern
    '''
    self.files_to_download = file_list



class DirectHttpDownload(DirectFTPDownload):

  def __init__(self, protocol, host, rootdir='', file_list=[]):
    '''
    :param file_list: list of files to download on server
    :type file_list: list
    '''
    DirectFTPDownload.__init__(self, protocol, host, rootdir, file_list)
    self.save_as = None
    self.method = 'GET'
    self.param = {}

  def download(self, local_dir, keep_dirs=True):
    '''
    Download remote files to local_dir

    :param local_dir: Directory where files should be downloaded
    :type local_dir: str
    :param keep_dirs: keep file name directory structure or copy file in local_dir directly
    :param keep_dirs: bool
    :return: list of downloaded files
    '''
    logging.debug('DirectHTTP:Download')
    nb_files = len(self.files_to_download)

    if nb_files > 1:
      self.files_to_download = []
      logging.error('DirectHTTP accepts only 1 file')

    cur_files = 1

    for rfile in self.files_to_download:
      if self.save_as is None:
        self.save_as = rfile['name']
      file_dir = local_dir
      if keep_dirs:
        file_dir = local_dir + os.path.dirname(self.save_as)
      file_path = file_dir + '/' + os.path.basename(self.save_as)
      if not os.path.exists(file_dir):
        os.makedirs(file_dir)
      logging.debug(str(cur_files)+'/'+str(nb_files)+' downloading file '+rfile['name']+', save as '+self.save_as)
      cur_files += 1
      if not 'url' in rfile:
        rfile['url'] = self.url
      fp = open(file_path, "wb")
      curl = pycurl.Curl()

      if self.method == 'POST':
        # Form data must be provided already urlencoded.
        postfields = urllib.urlencode(self.param)
        # Sets request method to POST,
        # Content-Type header to application/x-www-form-urlencoded
        # and data to send in request body.
        if self.credentials is not None:
          curl.setopt(pycurl.USERPWD, self.credentials)

        curl.setopt(pycurl.POSTFIELDS, postfields)
        curl.setopt(pycurl.URL, rfile['url']+rfile['root']+'/'+rfile['name'])
      else:
        url = rfile['url']+rfile['root']+'/'+rfile['name']+'?'+urllib.urlencode(self.param)
        curl.setopt(pycurl.URL, url)

      curl.setopt(pycurl.WRITEDATA, fp)
      curl.perform()

      curl.close()
      fp.close()
      logging.debug('downloaded!')
      rfile['name'] = self.save_as
      self.set_permissions(file_path, rfile)

    return self.files_to_download

  def list(self, directory=''):
    '''
    Try to get file headers to get last_modification and size
    '''
    for file in self.files_to_download:
      self.crl.setopt(pycurl.HEADER, True)
      if self.credentials is not None:
        curl.setopt(pycurl.USERPWD, self.credentials)

      self.crl.setopt(pycurl.NOBODY, True)
      self.crl.setopt(pycurl.URL, self.url+self.rootdir+file['name'])
      output = StringIO.StringIO()
      # lets assign this buffer to pycurl object
      self.crl.setopt(pycurl.WRITEFUNCTION, output.write)
      self.crl.perform()
      # lets get the output in a string
      result = output.getvalue()
      lines = re.split(r'[\n\r]+', result)
      for line in lines:
        parts = line.split(':')
        if parts[0].strip() == 'Content-Length':
          file['size'] = parts[1].strip()
        if parts[0].strip() == 'Last-Modified':
          # Sun, 06 Nov 1994
          res = re.match('(\w+),\s+(\d+)\s+(\w+)\s+(\d+)', parts[1].strip())
          if res:
            file['day'] = res.group(2)
            file['month'] = Utils.month_to_num(res.group(3))
            file['year'] = res.group(4)
            continue
          #Sunday, 06-Nov-94
          res = re.match('(\w+),\s+(\d+)-(\w+)-(\d+)', parts[1].strip())
          if res:
            file['day'] = res.group(2)
            file['month'] = Utils.month_to_num(res.group(3))
            file['year'] = str(2000 + int(res.group(4)))
            continue
          #Sun Nov  6 08:49:37 1994
          res = re.match('(\w+)\s+(\w+)\s+(\d+)\s+\d{2}:\d{2}:\d{2}\s+(\d+)', parts[1].strip())
          if res:
            file['day'] = res.group(3)
            file['month'] = Utils.month_to_num(res.group(2))
            file['year'] = res.group(4)
            continue
    return (self.files_to_download,[])
