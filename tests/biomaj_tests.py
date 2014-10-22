from nose.tools import *

import shutil
import os
import tempfile

from biomaj.bank import Bank
from biomaj.session import Session
from biomaj.workflow import Workflow
from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload

import unittest

class TestBiomajUtils(unittest.TestCase):

  def test_copy(self):
    from_dir = os.path.dirname(os.path.realpath(__file__))
    to_dir = tempfile.mkdtemp('biomaj')
    Utils.copy_files(from_dir, to_dir, ['.*\.py'])
    self.assertTrue(os.path.exists(to_dir+'/biomaj_tests.py'))


class TestBiomajFTPDownload(unittest.TestCase):

  def test_ftp_list(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.close()
    self.assertTrue(len(file_list) > 1)

  def test_download(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match(['^alu.*\.gz$'], file_list, dir_list)
    ftpd.download('/tmp')
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download) == 2)

  def test_download_in_subdir(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match(['^/db/FASTA/alu.*\.gz$'], file_list, dir_list)
    ftpd.download('/tmp')
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download) == 2)


class TestBiomajSetup(unittest.TestCase):


  def setUp(self):
      curdir = os.path.dirname(os.path.realpath(__file__))
      Bank.load_config(os.path.join(curdir,'global.properties'))

      if not os.path.exists(os.path.join('/tmp/biomaj/config','alu.properties')):
        os.makedirs('/tmp/biomaj/config')

        shutil.copyfile(os.path.join(curdir,'alu.properties'),
                        os.path.join('/tmp/biomaj/config','alu.properties'))
      b = Bank('alu')
      b.delete()
      data_dir = Bank.config.get('GENERAL','data.dir')
      lock_file = os.path.join(data_dir,'alu.lock')
      if os.path.exists(lock_file):
        os.remove(lock_file)


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
      b.load_session()
      for key in b.session._session['status'].keys():
        self.assertFalse(b.session.get_status(key))

  def test_session_reload_notover(self):
      '''
      Checks a session is used if present
      '''
      b = Bank('alu')
      for i in range(1,5):
        s = Session('alu', Bank.config, b.config_bank)
        s._session['status'][Workflow.FLOW_INIT] = True
        b.session = s
        b.save_session()

      b = Bank('alu')
      b.load_session()
      self.assertTrue(b.session.get_status(Workflow.FLOW_INIT))

  def test_session_reload_over(self):
      '''
      Checks a session is not if over
      '''
      b = Bank('alu')
      for i in range(1,5):
        s = Session('alu', Bank.config, b.config_bank)
        s._session['status'][Workflow.FLOW_INIT] = True
        s._session['status'][Workflow.FLOW_OVER] = True
        b.session = s
        b.save_session()

      b = Bank('alu')
      b.load_session()
      self.assertFalse(b.session.get_status(Workflow.FLOW_INIT))

  def test_get_release(self):
      '''
      Get release
      '''
      b = Bank('alu')
      b.load_session()
      res = b.update()
      self.assertTrue(res)
      self.assertTrue(b.session._session['release'] is not None)
