from future import standard_library
standard_library.install_aliases()
from builtins import str
import datetime
import logging
import pycurl
import io
import os
import re
import urllib.request, urllib.parse, urllib.error

from biomaj.download.interface import DownloadInterface
from biomaj.download.ftp import FTPDownload
from biomaj.utils import Utils

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

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


    def match(self, patterns, file_list, dir_list=None, prefix='', submatch=False):
        if dir_list is None:
            dir_list = []
        self.files_to_download = []
        for d in self.downloaders:
            d.match(patterns, d.files_to_download, [], prefix, submatch)
        self.files_to_download = []
        for d in self.downloaders:
            self.files_to_download += d.files_to_download

    def download(self, local_dir):
        self.files_to_download = []
        for d in self.downloaders:
            if self.kill_received:
                raise Exception('Kill request received, exiting')
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

    def __init__(self, protocol, host, rootdir='', file_list=None):
        '''

        Initialize the files in list with today as last-modification date.
        Size is also preset to zero, size will be set after download

        :param file_list: list of files to download on server
        :type file_list: list
        '''
        FTPDownload.__init__(self, protocol, host, rootdir)
        if file_list is None:
            file_list = []
        today = datetime.date.today()
        self.files_to_download = []
        self.headers = {}
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
        return (self.files_to_download, [])

    def match(self, patterns, file_list, dir_list=None, prefix='', submatch=False):
        '''
        All files to download match, no pattern
        '''
        if dir_list is None:
            dir_list = []
        self.files_to_download = file_list



class DirectHttpDownload(DirectFTPDownload):

    def __init__(self, protocol, host, rootdir='', file_list=None):
        '''
        :param file_list: list of files to download on server
        :type file_list: list
        '''
        if file_list is None:
            file_list = []
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
            if self.kill_received:
                raise Exception('Kill request received, exiting')

            if self.save_as is None:
                self.save_as = rfile['name']
            file_dir = local_dir
            if keep_dirs:
                file_dir = local_dir + os.path.dirname(self.save_as)
            file_path = file_dir + '/' + os.path.basename(self.save_as)
            self.mkdir_lock.acquire()
            try:
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
            except Exception as e:
                logging.error(e)
            finally:
                self.mkdir_lock.release() # release lock, no matter what
            logging.debug('DirectHTTP:Download:Progress'+str(cur_files)+'/'+str(nb_files)+' downloading file '+rfile['name']+', save as '+self.save_as)
            cur_files += 1
            if not 'url' in rfile:
                rfile['url'] = self.url
            fp = open(file_path, "wb")
            curl = pycurl.Curl()

            if self.proxy is not None:
                curl.setopt(pycurl.PROXY, self.proxy)
                if self.proxy_auth is not None:
                    curl.setopt(pycurl.PROXYUSERPWD, self.proxy_auth)

            if self.method == 'POST':
                # Form data must be provided already urlencoded.
                postfields = urllib.parse.urlencode(self.param)
                # Sets request method to POST,
                # Content-Type header to application/x-www-form-urlencoded
                # and data to send in request body.
                if self.credentials is not None:
                    curl.setopt(pycurl.USERPWD, self.credentials)

                curl.setopt(pycurl.POSTFIELDS, postfields)
                try:
                    curl.setopt(pycurl.URL, rfile['url']+rfile['root']+'/'+rfile['name'])
                except Exception as a:
                    curl.setopt(pycurl.URL, (rfile['url']+rfile['root']+'/'+rfile['name']).encode('ascii', 'ignore'))
                #curl.setopt(pycurl.URL, rfile['url']+rfile['root']+'/'+rfile['name'])
            else:
                url = rfile['url']+rfile['root']+'/'+rfile['name']+'?'+urllib.parse.urlencode(self.param)
                #curl.setopt(pycurl.URL, url)
                try:
                    curl.setopt(pycurl.URL, url)
                except Exception as a:
                    curl.setopt(pycurl.URL, url.encode('ascii', 'ignore'))

            curl.setopt(pycurl.WRITEDATA, fp)
            curl.perform()

            curl.close()
            fp.close()
            logging.debug('downloaded!')
            rfile['name'] = self.save_as
            self.set_permissions(file_path, rfile)
            self.set_progress(1, nb_files)
        return self.files_to_download

    def header_function(self, header_line):
        # HTTP standard specifies that headers are encoded in iso-8859-1.
        # On Python 2, decoding step can be skipped.
        # On Python 3, decoding step is required.
        header_line = header_line.decode('iso-8859-1')

        # Header lines include the first status line (HTTP/1.x ...).
        # We are going to ignore all lines that don't have a colon in them.
        # This will botch headers that are split on multiple lines...
        if ':' not in header_line:
            return

        # Break the header line into header name and value.
        name, value = header_line.split(':', 1)

        # Remove whitespace that may be present.
        # Header lines include the trailing newline, and there may be whitespace
        # around the colon.
        name = name.strip()
        value = value.strip()

        # Header names are case insensitive.
        # Lowercase name here.
        name = name.lower()

        # Now we can actually record the header name and value.
        self.headers[name] = value

    def list(self, directory=''):
        '''
        Try to get file headers to get last_modification and size
        '''
        for file in self.files_to_download:
            self.crl.setopt(pycurl.HEADER, True)
            if self.credentials is not None:
                self.crl.setopt(pycurl.USERPWD, self.credentials)

            if self.proxy is not None:
                self.crl.setopt(pycurl.PROXY, self.proxy)
                if self.proxy_auth is not None:
                    self.crl.setopt(pycurl.PROXYUSERPWD, self.proxy_auth)

            self.crl.setopt(pycurl.NOBODY, True)
            try:
                self.crl.setopt(pycurl.URL, self.url+self.rootdir+file['name'])
            except Exception as a:
                self.crl.setopt(pycurl.URL, (self.url+self.rootdir+file['name']).encode('ascii', 'ignore'))
            #self.crl.setopt(pycurl.URL, self.url+self.rootdir+file['name'])
            output = BytesIO()
            # lets assign this buffer to pycurl object
            self.crl.setopt(pycurl.WRITEFUNCTION, output.write)
            self.crl.setopt(pycurl.HEADERFUNCTION, self.header_function)
            self.crl.perform()

            # Figure out what encoding was sent with the response, if any.
            # Check against lowercased header name.
            encoding = None
            if 'content-type' in self.headers:
                content_type = self.headers['content-type'].lower()
                match = re.search('charset=(\S+)', content_type)
                if match:
                    encoding = match.group(1)
            if encoding is None:
                # Default encoding for HTML is iso-8859-1.
                # Other content types may have different default encoding,
                # or in case of binary data, may have no encoding at all.
                encoding = 'iso-8859-1'

            # lets get the output in a string
            result = output.getvalue().decode(encoding)

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
        return (self.files_to_download, [])
