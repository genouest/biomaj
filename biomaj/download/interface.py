from builtins import str
from builtins import object
import os
import logging
import datetime
import time
import re
import tarfile
import zipfile

from biomaj.utils import Utils

from biomaj.mongo_connector import MongoConnector


class _FakeLock(object):
    '''
    Fake lock for downloaders not called by a Downloadthread
    '''

    def __init__(self):
        pass

    def acquire(self):
        pass

    def release(self):
        pass

class DownloadInterface(object):
    '''
    Main interface that all downloaders must extend
    '''

    files_num_threads = 4

    def __init__(self):
        self.files_to_download = []
        self.files_to_copy = []
        self.error = False
        self.credentials = None
        #bank name
        self.bank = None
        self.mkdir_lock = _FakeLock()
        self.kill_received = False
        self.proxy = None

    def set_proxy(self, proxy, proxy_auth=None):
        '''
        Use a proxy to connect to remote servers

        :param proxy: proxy to use (see http://curl.haxx.se/libcurl/c/CURLOPT_PROXY.html for format)
        :type proxy: str
        :param proxy_auth: proxy authentication if any (user:password)
        :type proxy_auth: str
        '''
        self.proxy = proxy
        self.proxy_auth = proxy_auth


    def set_progress(self, val, max):
        '''
        Update progress on download

        :param val: number of downloaded files since last progress
        :type val: int
        :param max: number of files to download
        :type max: int
        '''
        logging.debug('Download:progress:'+str(val)+'/'+str(max))
        if not self.bank:
            logging.debug('bank not specified, skipping record of download progress')
            return

        MongoConnector.banks.update({'name': self.bank},
                {'$inc': {'status.download.progress': val},
                '$set': {'status.download.total': max}})

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
                if not dir_list and pattern == '**/*':
                    # Take all and no more dirs, take all files
                    for rfile in file_list:
                        rfile['root'] = self.rootdir
                        if prefix != '':
                            rfile['name'] = prefix + '/' +rfile['name']
                        self.files_to_download.append(rfile)
                        logging.debug('Download:File:MatchRegExp:'+rfile['name'])
                    return
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



    def set_permissions(self, file_path, file_info):
        '''
        Sets file attributes to remote ones
        '''
        ftime = datetime.date(int(file_info['year']), int(file_info['month']), int(file_info['day']))
        settime = time.mktime(ftime.timetuple())
        os.utime(file_path, (settime, settime))

    def download_or_copy(self, available_files, root_dir, check_exists=True):
        '''
        If a file to download is available in available_files, copy it instead of downloading it.

        Update the instance variables files_to_download and files_to_copy

        :param available_files: list of files available in root_dir
        :type available files: list
        :param root_dir: directory where files are available
        :type root_dir: str
        :param check_exists: checks if file exists locally
        :type check_exists: bool
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
            for dfile in self.files_to_download:
                if index < len(new_or_modified_files) and \
                  dfile['name'] == new_or_modified_files[index][0]:
                    new_files_to_download.append(dfile)
                    index += 1
                else:
                    if not check_exists or os.path.exists(os.path.join(root_dir, dfile['name'])):
                        dfile['root'] = root_dir
                        self.files_to_copy.append(dfile)
                    else:
                        new_files_to_download.append(dfile)

        else:
            # Copy everything
            for dfile in self.files_to_download:
                if not check_exists or os.path.exists(os.path.join(root_dir, dfile['name'])):
                    dfile['root'] = root_dir
                    self.files_to_copy.apppend(dfile)
                else:
                    new_files_to_download.append(dfile)

        self.files_to_download = new_files_to_download


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

    def set_credentials(self, userpwd):
        '''
        Set credentials in format user:pwd

        :param userpwd: credentials
        :type userpwd: str
        '''
        self.credentials = userpwd

    def close(self):
        '''
        Close connection
        '''
        pass
