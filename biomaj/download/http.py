from future import standard_library
standard_library.install_aliases()
import logging
import pycurl
import io
import re
import os

from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

class HTTPDownload(FTPDownload):
    '''
    Base class to download files from HTTP

    Makes use of http.parse.dir.line etc.. regexps to extract page information

    protocol=http
    server=ftp.ncbi.nih.gov
    remote.dir=/blast/db/FASTA/

    remote.files=^alu.*\\.gz$

    '''

    def __init__(self, protocol, host, rootdir, config):
        FTPDownload.__init__(self, protocol, host, rootdir)
        self.config = config


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
        '''
        'http.parse.dir.line': r'<a[\s]+href="([\S]+)/".*alt="\[DIR\]">.*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})',
        'http.parse.file.line': r'<a[\s]+href="([\S]+)".*([\d]{2}-[\w\d]{2,5}-[\d]{4}\s[\d]{2}:[\d]{2})[\s]+([\d\.]+[MKG]{0,1})',
        'http.group.dir.name': 1,
        'http.group.dir.date': 2,
        'http.group.file.name': 1,
        'http.group.file.date': 2,
        'http.group.file.size': 3,
        '''

        rfiles = []
        rdirs = []

        dirs = re.findall(self.config.get('http.parse.dir.line'), result)
        if dirs is not None and len(dirs) > 0:
            for founddir in dirs:
                rfile = {}
                rfile['permissions'] = ''
                rfile['group'] = ''
                rfile['user'] = ''
                rfile['size'] = '0'
                date = founddir[int(self.config.get('http.group.dir.date'))-1]
                dirdate = date.split()
                parts = dirdate[0].split('-')
                #19-Jul-2014 13:02
                rfile['month'] = Utils.month_to_num(parts[1])
                rfile['day'] = parts[0]
                rfile['year'] = parts[2]
                rfile['name'] = founddir[int(self.config.get('http.group.dir.name'))-1]
                rdirs.append(rfile)

        files = re.findall(self.config.get('http.parse.file.line'), result)
        if files is not None and len(files)>0:
            for foundfile in files:
                rfile = {}
                rfile['permissions'] = ''
                rfile['group'] = ''
                rfile['user'] = ''
                rfile['size'] = foundfile[int(self.config.get('http.group.file.size'))-1]
                date = foundfile[int(self.config.get('http.group.file.date'))-1]
                dirdate = date.split()
                parts = dirdate[0].split('-')
                #19-Jul-2014 13:02
                rfile['month'] = Utils.month_to_num(parts[1])
                rfile['day'] = parts[0]
                rfile['year'] = parts[2]
                rfile['name'] = foundfile[int(self.config.get('http.group.file.name'))-1]
                rfiles.append(rfile)

        return (rfiles, rdirs)
