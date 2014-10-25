from nose.tools import *
from nose.plugins.attrib import attr


import shutil
import os
import tempfile
import logging

from optparse import OptionParser


from biomaj.bank import Bank
from biomaj.session import Session
from biomaj.workflow import Workflow, UpdateWorkflow
from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload
from biomaj.download.copy  import LocalDownload
from biomaj.config import BiomajConfig

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
    self.bank_properties = ['alu', 'local']
    curdir = os.path.dirname(os.path.realpath(__file__))
    from_file = os.path.join(curdir, 'alu.properties')
    to_file = os.path.join(self.conf_dir, 'alu.properties')
    shutil.copyfile(from_file, to_file)

    # Manage local bank test, use bank test subdir as remote
    from_file = os.path.join(curdir, 'local.properties')
    to_file = os.path.join(self.conf_dir, 'local.properties')
    fout = open(to_file,'w')
    with open(from_file,'r') as fin:
      for line in fin:
        if line.startswith('remote.dir'):
          fout.write("remote.dir="+os.path.join(curdir,'bank')+"\n")
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
          else:
            fout.write(line)
    fout.close()


class TestBiomajUtils(unittest.TestCase):

  def setUp(self):
    self.utils = UtilsForTest()

  def tearDown(self):
    self.utils.clean()

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

    BiomajConfig.load_config(self.utils.global_properties)

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
    ftpd.match([r'^/db/FASTA/alu.*\.gz$'], file_list, dir_list)
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

class TestBiomajSetup(unittest.TestCase):


  def setUp(self):
    self.utils = UtilsForTest()
    curdir = os.path.dirname(os.path.realpath(__file__))
    BiomajConfig.load_config(self.utils.global_properties)

    b = Bank('alu')
    b.delete()

    self.config = BiomajConfig('alu')
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'alu.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)

  def tearDown(self):
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

@attr('network')
class TestBiomajFunctional(unittest.TestCase):

  def setUp(self):
    self.utils = UtilsForTest()
    curdir = os.path.dirname(os.path.realpath(__file__))
    BiomajConfig.load_config(self.utils.global_properties)

    b = Bank('alu')
    b.delete()

    self.config = BiomajConfig('alu')
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'alu.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)

  def tearDown(self):
    self.utils.clean()


  # Should test this on local downloader, changing 1 file to force update,
  # else we would get same bank and there would be no update
  #def test_no_update(self):
  #    '''
  #    Try updating twice, at second time, bank should be update
  #    '''
  #    b = Bank('alu')
  #    b.load_session(UpdateWorkflow.FLOW)
  #    b.update()
  #    self.assertTrue(b.session.get('update'))
  #    b.update()
  #    self.assertFalse(b.session.get('update'))
  #    self.assertFalse(b.session.get_status(Workflow.POSTPROCESS))
