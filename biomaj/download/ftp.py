import logging
import pycurl
import StringIO
import re
import os

from biomaj.utils import Utils
from biomaj.download.interface import DownloadInterface

class FTPDownload(DownloadInterface):
  '''
  Base class to download files from FTP

  protocol=ftp
  server=ftp.ncbi.nih.gov
  remote.dir=/blast/db/FASTA/

  remote.files=^alu.*\\.gz$

  '''


  def __init__(self, protocol, host, rootdir):
    DownloadInterface.__init__(self)
    logging.debug('Download')
    self.crl = pycurl.Curl()
    url = protocol+'://'+host
    self.rootdir = rootdir
    self.url = url


  def match(self, patterns, file_list, dir_list=[], prefix=''):
    '''
    Find files matching patterns. Sets instance variable files_to_download.

    :param patterns: regexps to match
    :type patterns: list
    :param file_list: list of files to match
    :type file_list: list
    :param dir_list: sub directories in current dir
    :type dir_list: list
    :param prefix: directory prefix
    :type prefix: str
    '''
    logging.debug('Download:File:RegExp:'+str(patterns))
    self.files_to_download = []
    for pattern in patterns:
      subdirs_pattern = pattern.split('/')
      if len(subdirs_pattern) > 1:
        # Pattern contains sub directories
        subdir = subdirs_pattern[0]
        if subdir == '^':
          subdirs_pattern = subdirs_pattern[1:]
          subdir = subdirs_pattern[0]
        logging.debug('Download:File:Subdir:Check:'+subdir)
        if re.match(subdirs_pattern[0], subdir):
          logging.debug('Download:File:Subdir:Match:'+subdir)
          # subdir match the beginning of the pattern
          # check match in subdir
          (subfile_list, subdirs_list) = self.list(prefix+'/'+subdir+'/')
          self.match(['/'.join(subdirs_pattern[1:])], subfile_list, subdirs_list, prefix+'/'+subdir)

      else:
        for rfile in file_list:
          if re.match(pattern, rfile['name']):
            rfile['root'] = self.rootdir
            if prefix != '':
              rfile['name'] = prefix + '/' +rfile['name']
            self.files_to_download.append(rfile)
            logging.debug('Download:File:MatchRegExp:'+rfile['name'])
    if len(self.files_to_download) == 0:
      raise Exception('no file found matching expressions')

  def download(self, local_dir):
    '''
    Download remote files to local_dir

    :param local_dir: Directory where files should be downloaded
    :type local_dir: str
    :return: list of downloaded files
    '''

    logging.warn('TODO: parallelize downloads')
    for rfile in self.files_to_download:
      file_dir = local_dir + os.path.dirname(rfile['name'])
      file_path = file_dir + '/' + os.path.basename(rfile['name'])
      if not os.path.exists(file_dir):
        os.makedirs(file_dir)

      fp = open(file_path, "wb")
      curl = pycurl.Curl()
      curl.setopt(pycurl.URL, self.url+rfile['root']+'/'+rfile['name'])
      curl.setopt(pycurl.WRITEDATA, fp)
      curl.perform()
      curl.close()
      fp.close()
      self.set_permissions(file_path, rfile)
    return self.files_to_download

  def list(self, directory=''):
    '''
    List FTP directory

    :return: tuple of file and dirs in current directory with details
    '''
    logging.debug('Download:List:'+self.url+self.rootdir+directory)
    self.crl.setopt(pycurl.URL, self.url+self.rootdir+directory)
    output = StringIO.StringIO()
    # lets assign this buffer to pycurl object
    self.crl.setopt(pycurl.WRITEFUNCTION, output.write)
    self.crl.perform()
    # lets get the output in a string
    result = output.getvalue()
    # FTP LIST output is separated by \r\n
    # lets split the output in lines
    #lines = result.split(r'[\r\n]+')
    lines = re.split(r'[\n\r]+', result)
    # lets walk through each line
    rfiles = []
    rdirs = []
    for line in lines:
        rfile = {}
        # lets print each part separately
        parts = line.split()
        # the individual fields in this list of parts
        if not parts: continue
        rfile['permissions'] = parts[0]
        rfile['group'] = parts[2]
        rfile['user'] = parts[3]
        rfile['size'] = parts[4]
        rfile['month'] = Utils.month_to_num(parts[5])
        rfile['day'] = parts[6]
        rfile['year'] = parts[7]
        rfile['name'] = parts[8]
        is_dir = False
        if re.match('^d', rfile['permissions']):
          is_dir = True

        if not is_dir:
          rfiles.append(rfile)
        else:
          rdirs.append(rfile)
    return (rfiles, rdirs)


  def chroot(self, cwd):
    logging.debug('Download: change dir '+cwd)

  def close(self):
    self.crl.close()
