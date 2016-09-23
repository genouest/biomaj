from future import standard_library
standard_library.install_aliases()
from builtins import str
import logging
import pycurl
import io
import re
import os
from datetime import datetime
import hashlib
import sys
import subprocess

from biomaj.utils import Utils
from biomaj.download.interface import DownloadInterface


class RSYNCDownload(DownloadInterface):
    '''
    Base class to download files from rsyncc
    protocol = rsync
    server = 
    remote.dir = 
        
    remote.files = 
    '''
        
    def __init__(self, protocol, server, remote_dir ):
        DownloadInterface.__init__(self)
        logging.debug('Download')
        self.rootdir = remote_dir
        self.protocol = protocol
        if server and remote_dir:
            self.server = server#name of the remote server
            self.remote_dir = remote_dir# directory on the remote server
        else:
            if server:
                self.server = server
                self.remote_dir = ""   

#---------------------------------------------------------------
    def list(self,directory=''):
        '''
        List server directory
        
        :return: dict of file and dirs in current directory with details
        '''
        err_code = None
        rfiles = []
        rdirs = []
        if self.remote_dir and self.credentials:
            cmd = str(self.protocol) + " --list-only " + str(self.credentials) + "@" + str(self.server) + ":" + str(self.remote_dir) + str(directory)
        elif (self.remote_dir and not self.credentials):
           cmd = str(self.protocol) + " --list-only " + str(self.server) + ":" + str(self.remote_dir) + str(directory) 
        else : #Local rsync for unitest 
            cmd = str(self.protocol) + " --list-only " + str(self.server)
        try:
            p = subprocess.Popen(cmd, stdin = subprocess.PIPE,stdout = subprocess.PIPE,stderr = subprocess.PIPE,shell = True)
            list_rsync, err = p.communicate()
            self.test_stderr_rsync_message(err)
            self.test_stderr_rsync_error(err)   
            err_code = p.returncode
        except ExceptionRsync, e:
            logging.error("RsyncError:" + str(e))
        if err_code !=  0:
            logging.error('Error while listing ' + str(err_code))
            return(rfiles, rdirs)
        
        for i in range(0,(len(list_rsync.rstrip().split("\n"))-1)):
            rfile = {}
            #rsync LIST output is separated by \n                        
            parts = list_rsync.rstrip().split("\n")[i].split()
            if not parts: continue
            date =  parts[2].split("/")
            rfile['permissions'] = parts[0]
            rfile['size'] = parts[1]
            rfile['month'] = date[1]
            rfile['day'] = date[2]
            rfile['year'] = date[0]
            rfile['name'] = parts[4]
            is_dir = False
            if re.match('^d', rfile['permissions']):
                is_dir = True
            
            if not is_dir:
                rfiles.append(rfile)
            else:
                rdirs.append(rfile)    
        
        return (rfiles, rdirs)
#---------------------------------------------------------------        
    def download(self, local_dir, keep_dirs = True):
        '''
        Download remote files to local_dir

        :param local_dir: Directory where files should be downloaded
        :type local_dir: str
        :param keep_dirs: keep file name directory structure or copy file in local_dir directly
        :param keep_dirs: bool
        :return: list of downloaded files
        '''
        
        logging.debug('RSYNC:Download')
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
            if re.match('\S*\/$',file_dir):
                file_path = file_dir + '/' + os.path.basename(rfile['save_as'])
            else:
                file_path = file_dir + os.path.basename(rfile['save_as'])
            # For unit tests only, workflow will take in charge directory creation before to avoid thread multi access
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)        
        
            logging.debug('RSYNC:Download:Progress:' + str(cur_files) + '/' + str(nb_files) + ' downloading file ' + rfile['name'])
            logging.debug('RSYNC:Download:Progress:' + str(cur_files) + '/' + str(nb_files) + ' save as ' + rfile['save_as'])
            cur_files += 1
            
            error = self.rsync_download(file_path,rfile['name'])
            if error:
                raise Exception("RSYNC:Download:Error:" + rfile['root'] + '/' + rfile['name'])
            self.set_permissions(file_path, rfile)
            #Add progress only per 10 files to limit db requests
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
        return(error,self.files_to_download)
        
#---------------------------------------------------------------
    def rsync_download(self,file_path, file_to_download):
        error = False
        err_code = ''
        try :
            if self.remote_dir and self.credentials: #download on server
                cmd = str(self.protocol) + " " + str(self.credentials) + "@" + str(self.server) + ":" + str(self.remote_dir) + str(file_to_download) + " " + str(file_path)
            elif self.remote_dir and not self.credentials:
                cmd = str(self.protocol) + " " + str(self.server) + ":" + str(self.remote_dir) + str(file_to_download) + " " + str(file_path)
            else: ##Local rsync for unitest 
                cmd = str(self.protocol) + " " + str(self.server) + str(file_to_download) + " " + str(file_path)
            p = subprocess.Popen(cmd, stdin = subprocess.PIPE,stderr = subprocess.PIPE,stdout = subprocess.PIPE,shell = True)
            stdout, stderr = p.communicate()
            err_code = p.returncode
            self.test_stderr_rsync_message(stderr)
            self.test_stderr_rsync_error(stderr)                      
        except ExceptionRsync, e:
            logging.error("RsyncError:" + str(e))
        if err_code !=  0:
            logging.error('Error while downloading ' + file_to_download + ' - ' + str(err_code))
            error = True
        return(error)
#---------------------------------------------------------------
    def test_stderr_rsync_error(self, stderr):
        if str(self.protocol) + " error" in stderr:
            reason = stderr.split(str(self.protocol) + " error:")[1].split("\n")[0]
            raise ExceptionRsync(reason)
#---------------------------------------------------------------
    def test_stderr_rsync_message(self, stderr):
        if str(self.protocol) + "" in stderr:
            reason = stderr.split(str(self.protocol) + ":")[1].split("\n")[0]
            raise ExceptionRsync(reason)

#____________________________________________________________________
class ExceptionRsync(Exception):
    def __init__(self, exception_reason):
        self.exception_reason = exception_reason
    def __str__(self):
        return self.exception_reason


        






        
    
        
