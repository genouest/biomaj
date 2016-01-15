from nose.tools import *
from nose.plugins.attrib import attr

import json
import shutil
import os
import tempfile
import logging
import copy
import stat
import time

from mock import patch

from optparse import OptionParser


from biomaj.bank import Bank
from biomaj.session import Session
from biomaj.workflow import Workflow, UpdateWorkflow
from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload
from biomaj.download.direct import DirectFTPDownload, DirectHttpDownload
from biomaj.download.http import HTTPDownload
from biomaj.download.localcopy  import LocalDownload
from biomaj.download.downloadthreads import DownloadThread
from biomaj.config import BiomajConfig
from biomaj.process.processfactory import PostProcessFactory,PreProcessFactory,RemoveProcessFactory
from biomaj.user import BmajUser
from biomaj.bmajindex import BmajIndex

from ldap3.core.exceptions import LDAPBindError


import unittest

class UtilsForTest():
  '''
  Copy properties files to a temp directory and update properties to
  use a temp directory
  '''

  def __init__(self):
    '''
    Setup the temp dirs and files.
    '''
    self.global_properties = None
    self.bank_properties = None

    self.test_dir = tempfile.mkdtemp('biomaj')

    self.conf_dir =os.path.join(self.test_dir,'conf')
    if not os.path.exists(self.conf_dir):
      os.makedirs(self.conf_dir)
    self.data_dir =os.path.join(self.test_dir,'data')
    if not os.path.exists(self.data_dir):
      os.makedirs(self.data_dir)
    self.log_dir =os.path.join(self.test_dir,'log')
    if not os.path.exists(self.log_dir):
      os.makedirs(self.log_dir)
    self.process_dir =os.path.join(self.test_dir,'process')
    if not os.path.exists(self.process_dir):
      os.makedirs(self.process_dir)
    self.lock_dir =os.path.join(self.test_dir,'lock')
    if not os.path.exists(self.lock_dir):
      os.makedirs(self.lock_dir)
    self.cache_dir =os.path.join(self.test_dir,'cache')
    if not os.path.exists(self.cache_dir):
      os.makedirs(self.cache_dir)


    if self.global_properties is None:
      self.__copy_global_properties()

    if self.bank_properties is None:
      self.__copy_test_bank_properties()

  def clean(self):
    '''
    Deletes temp directory
    '''
    shutil.rmtree(self.test_dir)

  def __copy_test_bank_properties(self):
    if self.bank_properties is not None:
      return
    self.bank_properties = ['alu', 'local', 'testhttp','directhttp']
    curdir = os.path.dirname(os.path.realpath(__file__))
    for b in self.bank_properties:
        from_file = os.path.join(curdir, b+'.properties')
        to_file = os.path.join(self.conf_dir, b+'.properties')
        shutil.copyfile(from_file, to_file)

    self.bank_process = ['test.sh']
    curdir = os.path.dirname(os.path.realpath(__file__))
    procdir = os.path.join(curdir, 'bank/process')
    for proc in self.bank_process:
      from_file = os.path.join(procdir, proc)
      to_file = os.path.join(self.process_dir, proc)
      shutil.copyfile(from_file, to_file)
      os.chmod(to_file, stat.S_IRWXU)

    # Manage local bank test, use bank test subdir as remote
    properties = ['multi.properties', 'computederror.properties', 'error.properties', 'local.properties', 'localprocess.properties', 'testhttp.properties', 'computed.properties', 'computed2.properties', 'sub1.properties', 'sub2.properties']
    for prop in properties:
      from_file = os.path.join(curdir, prop)
      to_file = os.path.join(self.conf_dir, prop)
      fout = open(to_file,'w')
      with open(from_file,'r') as fin:
        for line in fin:
          if line.startswith('remote.dir'):
            fout.write("remote.dir="+os.path.join(curdir,'bank')+"\n")
          elif line.startswith('remote.files'):
            fout.write(line.replace('/tmp', os.path.join(curdir,'bank')))
          else:
            fout.write(line)
      fout.close()

  def __copy_global_properties(self):
    if self.global_properties is not None:
      return
    self.global_properties = os.path.join(self.conf_dir,'global.properties')
    curdir = os.path.dirname(os.path.realpath(__file__))
    global_template = os.path.join(curdir,'global.properties')
    fout = open(self.global_properties,'w')
    with open(global_template,'r') as fin:
        for line in fin:
          if line.startswith('conf.dir'):
            fout.write("conf.dir="+self.conf_dir+"\n")
          elif line.startswith('log.dir'):
            fout.write("log.dir="+self.log_dir+"\n")
          elif line.startswith('data.dir'):
            fout.write("data.dir="+self.data_dir+"\n")
          elif line.startswith('process.dir'):
            fout.write("process.dir="+self.process_dir+"\n")
          elif line.startswith('lock.dir'):
            fout.write("lock.dir="+self.lock_dir+"\n")
          else:
            fout.write(line)
    fout.close()


class TestBiomajUtils(unittest.TestCase):

  def setUp(self):
    self.utils = UtilsForTest()

  def tearDown(self):
    self.utils.clean()


  def test_mimes(self):
    fasta_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),'bank/test2.fasta')
    (mime, encoding) = Utils.detect_format(fasta_file)
    self.assertTrue('application/fasta' == mime)

  @attr('compress')
  def test_uncompress(self):
    from_file = { 'root': os.path.dirname(os.path.realpath(__file__)),
                  'name': 'bank/test.fasta.gz'
                  }

    to_dir = self.utils.data_dir
    Utils.copy_files([from_file], to_dir)
    Utils.uncompress(os.path.join(to_dir, from_file['name']))
    self.assertTrue(os.path.exists(to_dir+'/bank/test.fasta'))

  def test_copy_with_regexp(self):
    from_dir = os.path.dirname(os.path.realpath(__file__))
    to_dir = self.utils.data_dir
    Utils.copy_files_with_regexp(from_dir, to_dir, ['.*\.py'])
    self.assertTrue(os.path.exists(to_dir+'/biomaj_tests.py'))

  def test_copy(self):
    from_dir = os.path.dirname(os.path.realpath(__file__))
    local_file = 'biomaj_tests.py'
    files_to_copy = [ {'root': from_dir, 'name': local_file}]
    to_dir = self.utils.data_dir
    Utils.copy_files(files_to_copy, to_dir)
    self.assertTrue(os.path.exists(to_dir+'/biomaj_tests.py'))

class TestBiomajLocalDownload(unittest.TestCase):
  '''
  Test Local downloader
  '''

  def setUp(self):
    self.utils = UtilsForTest()

    self.curdir = os.path.dirname(os.path.realpath(__file__))
    self.examples = os.path.join(self.curdir,'bank') + '/'

    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)

    '''
    if not os.path.exists('/tmp/biomaj/config'):
      os.makedirs('/tmp/biomaj/config')
    if not os.path.exists(os.path.join('/tmp/biomaj/config','local.properties')):
      shutil.copyfile(os.path.join(self.curdir,'local.properties'),
                      os.path.join('/tmp/biomaj/config','local.properties'))
      flocal = open(os.path.join('/tmp/biomaj/config','local.properties'),'a')
      flocal.write('\nremote.dir='+self.examples+"\n")
      flocal.close()
    '''

  def tearDown(self):
    self.utils.clean()

  def test_local_list(self):
    locald = LocalDownload(self.examples)
    (file_list, dir_list) = locald.list()
    locald.close()
    self.assertTrue(len(file_list) > 1)

  def test_local_download(self):
    locald = LocalDownload(self.examples)
    (file_list, dir_list) = locald.list()
    locald.match([r'^test.*\.gz$'], file_list, dir_list)
    locald.download(self.utils.data_dir)
    locald.close()
    self.assertTrue(len(locald.files_to_download) == 1)

  def test_local_download_in_subdir(self):
    locald = LocalDownload(self.curdir+'/')
    (file_list, dir_list) = locald.list()
    locald.match([r'^/bank/test.*\.gz$'], file_list, dir_list)
    locald.download(self.utils.data_dir)
    locald.close()
    self.assertTrue(len(locald.files_to_download) == 1)

  def test_parallel_local_download(self):
    locald = LocalDownload(self.examples)
    (file_list, dir_list) = locald.list()
    locald.match([r'^test'], file_list, dir_list)
    list1 = [locald.files_to_download[0]]
    list2 = locald.files_to_download[1:]
    locald.close()

    locald1 = LocalDownload(self.examples)
    locald1.files_to_download = list1
    locald2 = LocalDownload(self.examples)
    locald2.files_to_download = list2
    t1 = DownloadThread(locald1, self.utils.data_dir)
    t2 = DownloadThread(locald2, self.utils.data_dir)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    self.assertTrue(len(t1.downloader.files_to_download) == 1)
    self.assertTrue(os.path.exists(self.utils.data_dir + '/' +list1[0]['name']))
    self.assertTrue(len(t2.downloader.files_to_download) == 2)
    self.assertTrue(os.path.exists(self.utils.data_dir + '/' +list2[0]['name']))
    self.assertTrue(os.path.exists(self.utils.data_dir + '/' +list2[1]['name']))

@attr('network')
@attr('http')
class TestBiomajHTTPDownload(unittest.TestCase):
  '''
  Test HTTP downloader
  '''
  def setUp(self):
    self.utils = UtilsForTest()
    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)
    self.config = BiomajConfig('testhttp')

  def tearDown(self):
    self.utils.clean()

  def test_http_list(self):
    httpd = HTTPDownload('http', 'ftp2.fr.debian.org', '/debian/dists/', self.config)
    (file_list, dir_list) = httpd.list()
    httpd.close()
    self.assertTrue(len(file_list) == 1)

  def test_http_download(self):
    httpd = HTTPDownload('http', 'ftp2.fr.debian.org', '/debian/dists/', self.config)
    (file_list, dir_list) = httpd.list()
    httpd.match([r'^README$'], file_list, dir_list)
    httpd.download(self.utils.data_dir)
    httpd.close()
    self.assertTrue(len(httpd.files_to_download) == 1)

  def test_http_download_in_subdir(self):
    httpd = HTTPDownload('http', 'ftp2.fr.debian.org', '/debian/', self.config)
    (file_list, dir_list) = httpd.list()
    httpd.match([r'^dists/README$'], file_list, dir_list)
    httpd.download(self.utils.data_dir)
    httpd.close()
    self.assertTrue(len(httpd.files_to_download) == 1)


@attr('directftp')
@attr('network')
class TestBiomajDirectFTPDownload(unittest.TestCase):
  '''
  Test DirectFTP downloader
  '''

  def setUp(self):
    self.utils = UtilsForTest()

  def tearDown(self):
    self.utils.clean()

  def test_ftp_list(self):
    file_list = ['/blast/db/FASTA/alu.n.gz.md5']
    ftpd = DirectFTPDownload('ftp', 'ftp.ncbi.nih.gov', '', file_list)
    (file_list, dir_list) = ftpd.list()
    ftpd.close()
    self.assertTrue(len(file_list) == 1)

  def test_download(self):
    file_list = ['/blast/db/FASTA/alu.n.gz.md5']
    ftpd = DirectFTPDownload('ftp', 'ftp.ncbi.nih.gov', '', file_list)
    (file_list, dir_list) = ftpd.list()
    ftpd.download(self.utils.data_dir, False)
    ftpd.close()
    self.assertTrue(os.path.exists(os.path.join(self.utils.data_dir,'alu.n.gz.md5')))


@attr('directhttp')
@attr('network')
class TestBiomajDirectHTTPDownload(unittest.TestCase):
  '''
  Test DirectFTP downloader
  '''

  def setUp(self):
    self.utils = UtilsForTest()

  def tearDown(self):
    self.utils.clean()

  def test_http_list(self):
    file_list = ['/debian/README.html']
    ftpd = DirectHttpDownload('http', 'ftp2.fr.debian.org', '', file_list)
    fday = ftpd.files_to_download[0]['day']
    fmonth = ftpd.files_to_download[0]['month']
    fyear = ftpd.files_to_download[0]['year']
    (file_list, dir_list) = ftpd.list()
    ftpd.close()
    self.assertTrue(len(file_list) == 1)
    self.assertTrue(file_list[0]['size']!=0)
    self.assertFalse(fyear == ftpd.files_to_download[0]['year'] and fmonth == ftpd.files_to_download[0]['month'] and fday == ftpd.files_to_download[0]['day'])

  def test_download(self):
    file_list = ['/debian/README.html']
    ftpd = DirectHttpDownload('http', 'ftp2.fr.debian.org', '', file_list)
    (file_list, dir_list) = ftpd.list()
    ftpd.download(self.utils.data_dir, False)
    ftpd.close()
    self.assertTrue(os.path.exists(os.path.join(self.utils.data_dir,'README.html')))

  def test_download_get_params_save_as(self):
    file_list = ['/get']
    ftpd = DirectHttpDownload('http', 'httpbin.org', '', file_list)
    ftpd.param = { 'key1': 'value1', 'key2': 'value2'}
    ftpd.save_as = 'test.json'
    (file_list, dir_list) = ftpd.list()
    ftpd.download(self.utils.data_dir, False)
    ftpd.close()
    self.assertTrue(os.path.exists(os.path.join(self.utils.data_dir,'test.json')))
    with open(os.path.join(self.utils.data_dir,'test.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      self.assertTrue(my_json['args']['key1'] == 'value1')

  def test_download_save_as(self):
    file_list = ['/debian/README.html']
    ftpd = DirectHttpDownload('http', 'ftp2.fr.debian.org', '', file_list)
    ftpd.save_as = 'test.html'
    (file_list, dir_list) = ftpd.list()
    ftpd.download(self.utils.data_dir, False)
    ftpd.close()
    self.assertTrue(os.path.exists(os.path.join(self.utils.data_dir,'test.html')))

  def test_download_post_params(self):
    #file_list = ['/debian/README.html']
    file_list = ['/post']
    ftpd = DirectHttpDownload('http', 'httpbin.org', '', file_list)
    #ftpd = DirectHttpDownload('http', 'ftp2.fr.debian.org', '', file_list)
    ftpd.param = { 'key1': 'value1', 'key2': 'value2'}
    ftpd.save_as = 'test.json'
    ftpd.method = 'POST'
    (file_list, dir_list) = ftpd.list()
    ftpd.download(self.utils.data_dir, False)
    ftpd.close()
    self.assertTrue(os.path.exists(os.path.join(self.utils.data_dir,'test.json')))
    with open(os.path.join(self.utils.data_dir,'test.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      self.assertTrue(my_json['form']['key1'] == 'value1')


@attr('ftp')
@attr('network')
class TestBiomajFTPDownload(unittest.TestCase):
  '''
  Test FTP downloader
  '''

  def setUp(self):
    self.utils = UtilsForTest()

  def tearDown(self):
    self.utils.clean()

  def test_ftp_list(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.close()
    self.assertTrue(len(file_list) > 1)

  def test_download(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match([r'^alu.*\.gz$'], file_list, dir_list)
    ftpd.download(self.utils.data_dir)
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download) == 2)


  def test_download_in_subdir(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match([r'^db/FASTA/alu.*\.gz$'], file_list, dir_list)
    ftpd.download(self.utils.data_dir)
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download) == 2)

  def test_download_or_copy(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/')
    ftpd.files_to_download = [
          {'name':'/test1', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test2', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test/test1', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test/test11', 'year': '2013', 'month': '11', 'day': '10', 'size': 10}
          ]
    available_files = [
          {'name':'/test1', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test12', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test3', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test/test1', 'year': '2013', 'month': '11', 'day': '10', 'size': 20},
          {'name':'/test/test11', 'year': '2013', 'month': '11', 'day': '10', 'size': 10}
          ]
    ftpd.download_or_copy(available_files, '/biomaj', False)
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download)==2)
    self.assertTrue(len(ftpd.files_to_copy)==2)

  def test_get_more_recent_file(self):
    files = [
          {'name':'/test1', 'year': '2013', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test2', 'year': '2013', 'month': '11', 'day': '12', 'size': 10},
          {'name':'/test/test1', 'year': '1988', 'month': '11', 'day': '10', 'size': 10},
          {'name':'/test/test11', 'year': '2013', 'month': '9', 'day': '23', 'size': 10}
          ]
    release = Utils.get_more_recent_file(files)
    self.assertTrue(release['year']=='2013')
    self.assertTrue(release['month']=='11')
    self.assertTrue(release['day']=='12')

class TestBiomajSetup(unittest.TestCase):


  def setUp(self):
    self.utils = UtilsForTest()
    curdir = os.path.dirname(os.path.realpath(__file__))
    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)

    # Delete all banks
    b = Bank('alu')
    b.banks.remove({})

    self.config = BiomajConfig('alu')
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'alu.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)

  def tearDown(self):
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'alu.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)
    self.utils.clean()

  def test_new_bank(self):
    '''
    Checks bank init
    '''
    b = Bank('alu')

  def test_new_session(self):
    '''
    Checks an empty session is created
    '''
    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    for key in b.session._session['status'].keys():
      self.assertFalse(b.session.get_status(key))

  def test_session_reload_notover(self):
    '''
    Checks a session is used if present
    '''
    b = Bank('alu')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()

    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    self.assertTrue(b.session.get_status(Workflow.FLOW_INIT))

  def test_clean_old_sessions(self):
    '''
    Checks a session is used if present
    '''
    b = Bank('local')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()
    b2 = Bank('local')
    b2.update()
    b2.clean_old_sessions()
    self.assertTrue(len(b2.bank['sessions']) == 1)


  def test_session_reload_over(self):
    '''
    Checks a session if is not over
    '''
    b = Bank('alu')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      s._session['status'][Workflow.FLOW_OVER] = True
      b.session = s
      b.save_session()

    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    self.assertFalse(b.session.get_status(Workflow.FLOW_INIT))

  def test_bank_list(self):
    b1 = Bank('alu')
    b2 = Bank('local')
    banks = Bank.list()
    self.assertTrue(len(banks) == 2)

  @attr('network')
  def test_get_release(self):
    '''
    Get release
    '''
    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    res = b.update()
    self.assertTrue(b.session.get('update'))
    self.assertTrue(res)
    self.assertTrue(b.session._session['release'] is not None)

  def test_remove_session(self):
    b = Bank('alu')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()
    self.assertTrue(len(b.bank['sessions'])==4)
    b.remove_session(b.session.get('id'))
    self.assertTrue(len(b.bank['sessions'])==3)

  @attr('process')
  def test_postprocesses_setup(self):
    b = Bank('localprocess')
    pfactory = PostProcessFactory(b)
    pfactory.run(True)
    self.assertTrue(len(pfactory.threads_tasks[0])==2)
    self.assertTrue(len(pfactory.threads_tasks[1])==1)

  @attr('process')
  def test_postprocesses_exec_again(self):
    '''
    Execute once, set a status to false, check that False processes are executed
    '''
    b = Bank('localprocess')
    pfactory = PostProcessFactory(b)
    pfactory.run()
    self.assertTrue(pfactory.blocks['BLOCK1']['META0']['PROC0'])
    self.assertTrue(pfactory.blocks['BLOCK2']['META1']['PROC1'])
    self.assertTrue(pfactory.blocks['BLOCK2']['META1']['PROC2'])
    blocks = copy.deepcopy(pfactory.blocks)
    blocks['BLOCK2']['META1']['PROC2'] = False
    pfactory2 = PostProcessFactory(b, blocks)
    pfactory2.run()
    self.assertTrue(pfactory2.blocks['BLOCK2']['META1']['PROC2'])

  @attr('process')
  def test_preprocesses(self):
    b = Bank('localprocess')
    pfactory = PreProcessFactory(b)
    pfactory.run()
    self.assertTrue(pfactory.meta_status['META0']['PROC0'])

  @attr('process')
  def test_removeprocesses(self):
    b = Bank('localprocess')
    pfactory = RemoveProcessFactory(b)
    pfactory.run()
    self.assertTrue(pfactory.meta_status['META0']['PROC0'])

  def test_dependencies_list(self):
    b = Bank('computed')
    deps = b.get_dependencies()
    self.assertTrue(len(deps)==2)

class TestBiomajFunctional(unittest.TestCase):

  def setUp(self):
    self.utils = UtilsForTest()
    curdir = os.path.dirname(os.path.realpath(__file__))
    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)

    #Delete all banks
    b = Bank('local')
    b.banks.remove({})

    self.config = BiomajConfig('local')
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'local.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)

  def tearDown(self):
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'local.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)
    self.utils.clean()

  def test_extract_release_from_file_name(self):
    b = Bank('local')
    b.load_session(UpdateWorkflow.FLOW)
    b.session.config.set('release.file', 'test_(\d+)\.txt')
    b.session.config.set('release.regexp', '')
    w = UpdateWorkflow(b)
    w.wf_release()
    self.assertTrue(b.session.get('release') == '100')

  def test_extract_release_from_file_content(self):
    b = Bank('local')
    b.load_session(UpdateWorkflow.FLOW)
    b.session.config.set('release.file', 'test_100\.txt')
    b.session.config.set('release.regexp', 'Release\s*(\d+)')
    w = UpdateWorkflow(b)
    w.wf_release()
    self.assertTrue(b.session.get('release') == '103')

  def test_publish(self):
    '''
    Update a bank, then publish it
    '''
    b = Bank('local')
    b.update()
    current_link = os.path.join(b.config.get('data.dir'),
                                b.config.get('dir.version'),
                                'current')
    self.assertFalse(os.path.exists(current_link))
    self.assertTrue(b.bank['current'] is None)
    b.publish()
    self.assertTrue(os.path.exists(current_link))
    self.assertTrue(b.bank['current'] == b.session._session['id'])

  # Should test this on local downloader, changing 1 file to force update,
  # else we would get same bank and there would be no update
  def test_no_update(self):
      '''
      Try updating twice, at second time, bank should not be updated
      '''
      b = Bank('local')
      b.update()
      self.assertTrue(b.session.get('update'))
      b.update()
      self.assertFalse(b.session.get('update'))
      self.assertFalse(b.session.get_status(Workflow.FLOW_POSTPROCESS))

  @attr('release')
  def test_release_control(self):
    '''
    Try updating twice, at second time, modify one file (same date),
     bank should update
    '''
    b = Bank('local')
    b.update()
    b.session.config.set('keep.old.version', '3')
    self.assertTrue(b.session.get('update'))
    remote_file = b.session.config.get('remote.dir') + 'test2.fasta'
    os.utime(remote_file, None)
    # Update test2.fasta and set release.control
    b.session.config.set('release.control', 'true')
    b.update()
    self.assertTrue(b.session.get('update'))
    b.update()
    self.assertFalse(b.session.get('update'))
    b.session.config.set('remote.files', '^test2.fasta')
    b.update()
    self.assertTrue(b.session.get('update'))

  def test_fromscratch_update(self):
      '''
      Try updating twice, at second time, bank should  be updated (force with fromscratc)
      '''
      b = Bank('local')
      b.update()
      self.assertTrue(b.session.get('update'))
      sess = b.session.get('release')
      b.options.fromscratch = True
      b.update()
      self.assertTrue(b.session.get('update'))
      self.assertEqual(b.session.get('release'), sess+'__1')


  def test_fromscratch_update_with_release(self):
      '''
      Try updating twice, at second time, bank should  be updated (force with fromscratch)

      Use case with release defined in release file
      '''
      b = Bank('local')
      b.load_session(UpdateWorkflow.FLOW)
      b.session.config.set('release.file', 'test_(\d+)\.txt')
      b.session.config.set('release.regexp', '')
      w = UpdateWorkflow(b)
      w.wf_release()
      self.assertTrue(b.session.get('release') == '100')
      os.makedirs(b.session.get_full_release_directory())
      w = UpdateWorkflow(b)
      # Reset release
      b.session.set('release', None)
      w.options.fromscratch = True
      w.wf_release()
      self.assertTrue(b.session.get('release') == '100__1')


  def test_mix_stop_from_task(self):
      '''
      Get a first release, then fromscratch --stop-after, then restart from-task
      '''
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      self.assertTrue(b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      self.assertTrue(b3.session.get('release') == rel+'__1')
      self.assertTrue(res)

  def test_mix_stop_from_task2(self):
      '''
      Get a first release, then fromscratch --stop-after, then restart from-task
      '''
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      self.assertTrue(b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      b2.options.from_task = 'download'
      self.assertTrue(b3.session.get('release') == rel+'__1')
      self.assertTrue(res)

  def test_mix_stop_from_task3(self):
      '''
      Get a first release, then fromscratch --stop-after, then restart from-task
      '''
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      self.assertTrue(b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      b2.options.from_task = 'postprocess'
      self.assertTrue(b3.session.get('release') == rel+'__1')
      self.assertTrue(res)


  def test_mix_stop_from_task4(self):
      '''
      Get a first release, then fromscratch --stop-after, then restart from-task
      '''
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_before = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      b3 = Bank('local')
      b3.options.from_task = 'postprocess'
      res = b3.update()
      self.assertFalse(res)

  def test_delete_old_dirs(self):
      '''
      Try updating 3 times, oldest dir should be removed
      '''
      b = Bank('local')
      b.removeAll(True)
      b = Bank('local')
      b.update()
      self.assertTrue(b.session.get('update'))
      b.options.fromscratch = True
      b.update()
      self.assertTrue(b.session.get('update'))
      self.assertTrue(len(b.bank['production']) == 2)
      b.update()
      self.assertTrue(b.session.get('update'))
      # one new dir, but olders must be deleted
      self.assertTrue(len(b.bank['production']) == 2)

  def test_delete_old_dirs_with_freeze(self):
      '''
      Try updating 3 times, oldest dir should be removed but not freezed releases
      '''
      b = Bank('local')
      b.removeAll(True)
      b = Bank('local')
      b.update()
      b.freeze(b.session.get('release'))
      self.assertTrue(b.session.get('update'))
      b.options.fromscratch = True
      b.update()
      b.freeze(b.session.get('release'))
      self.assertTrue(b.session.get('update'))
      self.assertTrue(len(b.bank['production']) == 2)
      b.update()
      self.assertTrue(b.session.get('update'))
      # one new dir, but olders must be deleted
      self.assertTrue(len(b.bank['production']) == 3)


  def test_removeAll(self):
    b = Bank('local')
    b.update()
    b.removeAll()
    self.assertFalse(os.path.exists(b.get_data_dir()))
    bdb = b.banks.find_one({'name': b.name})
    self.assertTrue(bdb is None)

  def test_remove(self):
    '''
    test removal of a production dir
    '''
    b = Bank('local')
    b.update()
    self.assertTrue(os.path.exists(b.session.get_full_release_directory()))
    self.assertTrue(len(b.bank['production'])==1)
    b.remove(b.session.get('release'))
    self.assertFalse(os.path.exists(b.session.get_full_release_directory()))
    b = Bank('local')
    self.assertTrue(len(b.bank['production'])==0)

  def test_update_stop_after(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    self.assertTrue(b.session.get_status('download'))
    self.assertFalse(b.session.get_status('postprocess'))

  def test_update_stop_before(self):
    b = Bank('local')
    b.options.stop_before = 'postprocess'
    b.update()
    self.assertTrue(b.session.get_status('download'))
    self.assertFalse(b.session.get_status('postprocess'))

  def test_reupdate_from_task(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    self.assertFalse(b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    b2.update()
    self.assertTrue(b2.session.get_status('postprocess'))
    self.assertEqual(b.session.get_full_release_directory(), b2.session.get_full_release_directory())

  def test_reupdate_from_task_error(self):
    b = Bank('local')
    b.options.stop_after = 'check'
    b.update()
    self.assertFalse(b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    res = b2.update()
    self.assertFalse(res)

  def test_reupdate_from_task_wrong_release(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    self.assertFalse(b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = 'wrongrelease'
    res = b2.update()
    self.assertFalse(res)

  @attr('process')
  def test_postprocesses_restart_from_proc(self):
    b = Bank('localprocess')
    b.update()
    proc1file = os.path.join(b.session.get_full_release_directory(),'proc1.txt')
    proc2file = os.path.join(b.session.get_full_release_directory(),'proc2.txt')
    self.assertTrue(os.path.exists(proc1file))
    self.assertTrue(os.path.exists(proc2file))
    os.remove(proc1file)
    os.remove(proc2file)
    # Restart from postprocess, reexecute all processes
    b2 = Bank('localprocess')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    b2.update()
    self.assertTrue(os.path.exists(proc1file))
    self.assertTrue(os.path.exists(proc2file))
    os.remove(proc1file)
    os.remove(proc2file)
    # Restart from postprocess, but at process PROC2 and following
    b3 = Bank('localprocess')
    b3.options.from_task = 'postprocess'
    b3.options.process = 'PROC2'
    b3.options.release = b.session.get('release')
    b3.update()
    #self.assertFalse(os.path.exists(proc1file))
    self.assertTrue(os.path.exists(proc2file))

  def test_computed(self):
    b = Bank('computed')
    res = b.update(True)
    self.assertTrue(res)
    self.assertTrue(os.path.exists(b.session.get_full_release_directory()+'/sub1/flat/test_100.txt'))
    self.assertTrue(b.session.get('update'))
    # Check that, with depends non updated, bank is not updated itself
    nextb = Bank('computed')
    res = nextb.update(True)
    self.assertFalse(nextb.session.get('update'))


  @attr('nofile')
  def test_computed_nofile(self):
    b = Bank('computed2')
    b.load_session(UpdateWorkflow.FLOW)
    b.session.config.set('protocol', 'none')
    b.session.config.set('sub1.files.move', 'flat/test_.*')
    res = b.update(True)
    self.assertTrue(res)
    self.assertTrue(os.path.exists(b.session.get_full_release_directory()+'/sub1/flat/test_100.txt'))


  def test_computed_ref_release(self):
    b = Bank('computed2')
    res = b.update(True)
    b2 = Bank('sub1')
    b2release = b2.bank['production'][len(b2.bank['production'])-1]['release']
    brelease = b.bank['production'][len(b.bank['production'])-1]['release']
    self.assertTrue(res)
    self.assertTrue(brelease == b2release)

  @attr('computed')
  def test_computed_ref_release(self):
    b = Bank('computed2')
    res = b.update(True)
    self.assertTrue(b.session.get('update'))
    b2 = Bank('computed2')
    res = b2.update(True)
    self.assertFalse(b2.session.get('update'))

  def test_computederror(self):
    b = Bank('computederror')
    res = b.update(True)
    self.assertFalse(res)
    self.assertTrue(b.session._session['depends']['sub2'])
    self.assertFalse(b.session._session['depends']['error'])


  @attr('directrelease')
  def test_directhttp_release(self):
      b = Bank('directhttp')
      res = b.update()
      self.assertTrue(b.session.get('update'))
      self.assertTrue(os.path.exists(b.session.get_full_release_directory()+'/flat/debian/README.html'))
      #print str(b.session.get('release'))
      #print str(b.session.get('remoterelease'))

  @attr('network')
  def test_multi(self):
    b = Bank('multi')
    res = b.update()
    with open(os.path.join(b.session.get_full_release_directory(),'flat/test1.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      self.assertTrue(my_json['args']['key1'] == 'value1')
    with open(os.path.join(b.session.get_full_release_directory(),'flat/test2.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      self.assertTrue(my_json['form']['key1'] == 'value1')

  def test_freeze(self):
    b = Bank('local')
    b.update()
    rel = b.session.get('release')
    b.freeze(rel)
    prod = b.get_production(rel)
    self.assertTrue(prod['freeze'] == True)
    res = b.remove(rel)
    self.assertTrue(res == False)
    b.unfreeze(rel)
    prod = b.get_production(rel)
    self.assertTrue(prod['freeze'] == False)
    res = b.remove(rel)
    self.assertTrue(res == True)


  def test_stats(self):
    b = Bank('local')
    b.update()
    rel = b.session.get('release')
    stats = Bank.get_banks_disk_usage()
    self.assertTrue(stats[0]['size']>0)
    for release in stats[0]['releases']:
      if release['name'] == rel:
        self.assertTrue(release['size']>0)


  @attr('process')
  def test_processes_meta_data(self):
    b = Bank('localprocess')
    b.update()
    formats = b.session.get('formats')
    self.assertTrue(len(formats['blast'])==2)
    self.assertTrue(len(formats['test'][0]['files'])==3)

  @attr('process')
  def test_search(self):
    b = Bank('localprocess')
    b.update()
    search_res = Bank.search(['blast'],[])
    self.assertTrue(len(search_res)==1)
    search_res = Bank.search([],['nucleic'])
    self.assertTrue(len(search_res)==1)
    search_res = Bank.search(['blast'],['nucleic'])
    self.assertTrue(len(search_res)==1)
    search_res = Bank.search(['blast'],['proteic'])
    self.assertTrue(len(search_res)==0)


  def test_owner(self):
    '''
    test ACL with owner
    '''
    b = Bank('local')
    res = b.update()
    self.assertTrue(res)
    b.set_owner('sample')
    b2 = Bank('local')
    try:
      res = b2.update()
      self.fail('not owner, should not be allowed')
    except Exception as e:
      pass

@attr('elastic')
class TestElastic(unittest.TestCase):
    '''
    test indexing and search
    '''

    def setUp(self):
        BmajIndex.es = None
        self.utils = UtilsForTest()
        curdir = os.path.dirname(os.path.realpath(__file__))
        BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)
        if BmajIndex.do_index == False:
            self.skipTest("Skipping indexing tests due to elasticsearch not available")
        # Delete all banks
        b = Bank('local')
        b.banks.remove({})
        BmajIndex.delete_all_bank('local')

        self.config = BiomajConfig('local')
        data_dir = self.config.get('data.dir')
        lock_file = os.path.join(data_dir,'local.lock')
        if os.path.exists(lock_file):
          os.remove(lock_file)

    def tearDown(self):
        data_dir = self.config.get('data.dir')
        lock_file = os.path.join(data_dir,'local.lock')
        if os.path.exists(lock_file):
          os.remove(lock_file)
        self.utils.clean()
        BmajIndex.delete_all_bank('test')

    def test_index(self):
        BmajIndex.do_index = True
        prod = {
    			"data_dir" : "/tmp/test/data",
    			"formats" : {
    				"fasta" : [
    					{
    						"files" : [
    							"fasta/chr1.fa",
    							"fasta/chr2.fa"
    						],
    						"types" : [
    							"nucleic"
    						],
    						"tags" : {
    							"organism" : "hg19"
    						}
    					}
    				],
    				"blast": [
    					{
    						"files" : [
    							"blast/chr1/chr1db"
    						],
    						"types" : [
    							"nucleic"
    						],
    						"tags" : {
    							"chr" : "chr1",
    							"organism" : "hg19"
    						}
    					}
    				]

    			},
    			"freeze" : False,
    			"session" : 1416229253.930908,
    			"prod_dir" : "alu-2003-11-26",
    			"release" : "2003-11-26",
    			"types" : [
    				"nucleic"
    			]
    		}

        BmajIndex.add('test',prod, True)

        query = {
          'query' : {
            'match' : {'bank': 'test'}
            }
          }
        res = BmajIndex.search(query)
        self.assertTrue(len(res)==2)


    def test_remove_all(self):
        self.test_index()
        query = {
          'query' : {
            'match' : {'bank': 'test'}
            }
          }
        BmajIndex.delete_all_bank('test')
        res = BmajIndex.search(query)
        self.assertTrue(len(res)==0)


class MockLdapConn(object):

  ldap_user = 'biomajldap'
  ldap_user_email = 'bldap@no-reply.org'

  STRATEGY_SYNC = 0
  AUTH_SIMPLE = 0
  STRATEGY_SYNC = 0
  STRATEGY_ASYNC_THREADED = 0
  SEARCH_SCOPE_WHOLE_SUBTREE = 0
  GET_ALL_INFO = 0

  @staticmethod
  def Server(ldap_host, port, get_info):
      return None

  @staticmethod
  def Connection(ldap_server, auto_bind=True, read_only=True, client_strategy=0, user=None, password=None, authentication=0,check_names=True):
      if user is not None and password is not None:
          if password == 'notest':
              #raise ldap3.core.exceptions.LDAPBindError('no bind')
              return None
      return MockLdapConn(ldap_server)

  def __init__(self, url=None):
    #self.ldap_user = 'biomajldap'
    #self.ldap_user_email = 'bldap@no-reply.org'
    pass

  def search(self, base_dn, filter, scope, attributes=[]):
    if MockLdapConn.ldap_user in filter:
      self.response = [{'dn': MockLdapConn.ldap_user, 'attributes': {'mail': [MockLdapConn.ldap_user_email]}}]
      return [(MockLdapConn.ldap_user, {'mail': [MockLdapConn.ldap_user_email]})]
    else:
      raise Exception('no match')

  def unbind(self):
    pass


@attr('user')
class TestUser(unittest.TestCase):
  '''
  Test user management
  '''

  def setUp(self):
    self.utils = UtilsForTest()
    self.curdir = os.path.dirname(os.path.realpath(__file__))
    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)

  def tearDown(self):
    self.utils.clean()

  @patch('ldap3.Connection')
  def test_get_user(self, initialize_mock):
    mockldap = MockLdapConn()
    initialize_mock.return_value = MockLdapConn.Connection(None, None, None, None)
    user = BmajUser('biomaj')
    self.assertTrue(user.user is None)
    user.remove()

  @patch('ldap3.Connection')
  def test_create_user(self, initialize_mock):
    mockldap = MockLdapConn()
    initialize_mock.return_value = MockLdapConn.Connection(None, None, None, None)
    user = BmajUser('biomaj')
    user.create('test', 'test@no-reply.org')
    self.assertTrue(user.user['email'] == 'test@no-reply.org')
    user.remove()

  @patch('ldap3.Connection')
  def test_check_password(self, initialize_mock):
    mockldap = MockLdapConn()
    initialize_mock.return_value = MockLdapConn.Connection(None, None, None, None)
    user = BmajUser('biomaj')
    user.create('test', 'test@no-reply.org')
    self.assertTrue(user.check_password('test'))
    user.remove()


  @patch('ldap3.Connection')
  def test_ldap_user(self, initialize_mock):
    mockldap = MockLdapConn()
    initialize_mock.return_value = MockLdapConn.Connection(None, None, None, None)
    user = BmajUser('biomajldap')
    self.assertTrue(user.user['is_ldap'] == True)
    self.assertTrue(user.user['_id'] is not None)
    self.assertTrue(user.check_password('test'))
    user.remove()
