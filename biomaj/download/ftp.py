from future import standard_library
standard_library.install_aliases()
from builtins import str
import logging
import pycurl
import io
import re
import os
from datetime import datetime

from biomaj.utils import Utils
from biomaj.download.interface import DownloadInterface

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO


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
        self.headers = {}

    def match(self, patterns, file_list, dir_list=None, prefix='', submatch=False):
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
        :param submatch: first call to match, or called from match
        :type submatch: bool
        '''
        logging.debug('Download:File:RegExp:'+str(patterns))
        if dir_list is None:
            dir_list = []
        if not submatch:
            self.files_to_download = []
        for pattern in patterns:
            subdirs_pattern = pattern.split('/')
            if len(subdirs_pattern) > 1:
            # Pattern contains sub directories
                subdir = subdirs_pattern[0]
                if subdir == '^':
                    subdirs_pattern = subdirs_pattern[1:]
                    subdir = subdirs_pattern[0]
                for direlt in dir_list:
                    subdir = direlt['name']
                    logging.debug('Download:File:Subdir:Check:'+subdir)
                    if pattern == '**/*':
                        (subfile_list, subdirs_list) = self.list(prefix+'/'+subdir+'/')
                        self.match([pattern], subfile_list, subdirs_list, prefix+'/'+subdir, True)
                        for rfile in file_list:
                            if pattern == '**/*' or re.match(pattern, rfile['name']):
                                rfile['root'] = self.rootdir
                                if prefix != '':
                                    rfile['name'] = prefix + '/' +rfile['name']
                                self.files_to_download.append(rfile)
                                logging.debug('Download:File:MatchRegExp:'+rfile['name'])
                    else:
                        if re.match(subdirs_pattern[0], subdir):
                            logging.debug('Download:File:Subdir:Match:'+subdir)
                            # subdir match the beginning of the pattern
                            # check match in subdir
                            (subfile_list, subdirs_list) = self.list(prefix+'/'+subdir+'/')
                            self.match(['/'.join(subdirs_pattern[1:])], subfile_list, subdirs_list, prefix+'/'+subdir, True)

            else:
                for rfile in file_list:
                    if re.match(pattern, rfile['name']):
                        rfile['root'] = self.rootdir
                        if prefix != '':
                            rfile['name'] = prefix + '/' +rfile['name']
                        self.files_to_download.append(rfile)
                        logging.debug('Download:File:MatchRegExp:'+rfile['name'])
        if not submatch and len(self.files_to_download) == 0:
            raise Exception('no file found matching expressions')

    def download(self, local_dir, keep_dirs=True):
        '''
        Download remote files to local_dir

        :param local_dir: Directory where files should be downloaded
        :type local_dir: str
        :param keep_dirs: keep file name directory structure or copy file in local_dir directly
        :param keep_dirs: bool
        :return: list of downloaded files
        '''
        logging.debug('FTP:Download')

        nb_files = len(self.files_to_download)
        cur_files = 1

        for rfile in self.files_to_download:
            if self.kill_received:
                raise Exception('Kill request received, exiting')
            file_dir = local_dir
            if 'save_as' not in rfile or rfile['save_as'] is None:
                rfile['save_as'] = rfile['name']
            if keep_dirs:
                file_dir = local_dir + '/' + os.path.dirname(rfile['save_as'])
            file_path = file_dir + '/' + os.path.basename(rfile['save_as'])

            self.mkdir_lock.acquire()
            try:
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
            except Exception as e:
                logging.error(e)
            finally:
                self.mkdir_lock.release() # release lock, no matter what
            logging.debug('FTP:Download:Progress:'+str(cur_files)+'/'+str(nb_files)+' downloading file '+rfile['name'])
            logging.debug('FTP:Download:Progress:'+str(cur_files)+'/'+str(nb_files)+' save as '+rfile['save_as'])
            cur_files += 1
            if not 'url' in rfile:
                rfile['url'] = self.url
            fp = open(file_path, "wb")
            curl = pycurl.Curl()
            try:
                curl.setopt(pycurl.URL, rfile['url']+rfile['root']+'/'+rfile['name'])
            except Exception as a:
                curl.setopt(pycurl.URL, (rfile['url']+rfile['root']+'/'+rfile['name']).encode('ascii', 'ignore'))

            if self.proxy is not None:
                self.crl.setopt(pycurl.PROXY, self.proxy)
                if self.proxy_auth is not None:
                    curl.setopt(pycurl.PROXYUSERPWD, self.proxy_auth)

            if self.credentials is not None:
                curl.setopt(pycurl.USERPWD, self.credentials)
            curl.setopt(pycurl.WRITEDATA, fp)
            curl.perform()
            #errcode = curl.getinfo(pycurl.HTTP_CODE)
            #if int(errcode) != 200:
            #  self.error = True
            #  logging.error('Error while downloading '+rfile['name']+' - '+str(errcode))
            curl.close()
            fp.close()
            #logging.debug('downloaded!')
            self.set_permissions(file_path, rfile)
            # Add progress only per 10 files to limit db requests
            if nb_files < 10:
                nb = 1
                do_progress = True
            else:
                if cur_files == nb_files:
                    do_progress = True
                    nb = cur_files % 10
                elif cur_files > 0 and cur_files % 10 == 0:
                    nb = 10
                    do_progress = True
                else:
                    do_progress = False
            if do_progress:
                self.set_progress(nb, nb_files)
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
        List FTP directory

        :return: tuple of file and dirs in current directory with details
        '''
        logging.debug('Download:List:'+self.url+self.rootdir+directory)
        #self.crl.setopt(pycurl.URL, self.url+self.rootdir+directory)
        try:
            self.crl.setopt(pycurl.URL, self.url+self.rootdir+directory)
        except Exception as a:
            self.crl.setopt(pycurl.URL, (self.url+self.rootdir+directory).encode('ascii', 'ignore'))

        if self.proxy is not None:
            self.crl.setopt(pycurl.PROXY, self.proxy)
            if self.proxy_auth is not None:
                self.crl.setopt(pycurl.PROXYUSERPWD, self.proxy_auth)

        if self.credentials is not None:
            self.crl.setopt(pycurl.USERPWD, self.credentials)
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
            try:
                rfile['year'] = int(parts[7])
            except Exception as e:
                # specific ftp case issues at getting date info
                curdate = datetime.now()
                rfile['year'] = curdate.year
                # Year not precised, month feater than current means previous year
                if rfile['month'] > curdate.month:
                    rfile['year'] = curdate.year - 1
                # Same month but later day => previous year
                if rfile['month'] == curdate.month and int(rfile['day']) > curdate.day:
                    rfile['year'] = curdate.year - 1
            rfile['name'] = parts[8]
            if len(parts) >= 10 and parts[9] == '->':
                # Symlink, add to files AND dirs as we don't know the type of the link
                rdirs.append(rfile)

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
        if self.crl is not None:
            self.crl.close()
            self.crl = None
