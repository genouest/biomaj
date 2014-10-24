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
from biomaj.config import BiomajConfig

import unittest

class TestBiomajUtils(unittest.TestCase):

  def test_uncompress(self):
    from_file = { 'root': os.path.dirname(os.path.realpath(__file__)),
                  'name': 'bank/test.fasta.gz'
                  }

    to_dir = tempfile.mkdtemp('biomaj')
    Utils.copy_files([from_file], to_dir)
    Utils.uncompress(os.path.join(to_dir, from_file['name']))
    self.assertTrue(os.path.exists(to_dir+'/bank/test.fasta'))

  def test_copy_with_regexp(self):
    from_dir = os.path.dirname(os.path.realpath(__file__))
    to_dir = tempfile.mkdtemp('biomaj')
    Utils.copy_files_with_regexp(from_dir, to_dir, ['.*\.py'])
    self.assertTrue(os.path.exists(to_dir+'/biomaj_tests.py'))

  def test_copy(self):
    from_dir = os.path.dirname(os.path.realpath(__file__))
    local_file = 'biomaj_tests.py'
    files_to_copy = [ {'root': from_dir, 'name': local_file}]
    to_dir = tempfile.mkdtemp('biomaj')
    Utils.copy_files(files_to_copy, to_dir)
    self.assertTrue(os.path.exists(to_dir+'/biomaj_tests.py'))

@attr('network')
class TestBiomajFTPDownload(unittest.TestCase):

  def test_ftp_list(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.close()
    self.assertTrue(len(file_list) > 1)

  def test_download(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/db/FASTA/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match([r'^alu.*\.gz$'], file_list, dir_list)
    ftpd.download('/tmp')
    ftpd.close()
    self.assertTrue(len(ftpd.files_to_download) == 2)

  def test_download_in_subdir(self):
    ftpd = FTPDownload('ftp', 'ftp.ncbi.nih.gov', '/blast/')
    (file_list, dir_list) = ftpd.list()
    ftpd.match([r'^/db/FASTA/alu.*\.gz$'], file_list, dir_list)
    ftpd.download('/tmp')
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
      curdir = os.path.dirname(os.path.realpath(__file__))
      BiomajConfig.load_config(os.path.join(curdir,'global.properties'))

      if not os.path.exists(os.path.join('/tmp/biomaj/config','alu.properties')):
        os.makedirs('/tmp/biomaj/config')

        shutil.copyfile(os.path.join(curdir,'alu.properties'),
                        os.path.join('/tmp/biomaj/config','alu.properties'))
      b = Bank('alu')
      b.delete()
      self.config = BiomajConfig('alu')
      data_dir = self.config.get('data.dir')
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
      self.assertTrue(res)
      self.assertTrue(b.session._session['release'] is not None)

@attr('network')
class TestBiomajFunctional(unittest.TestCase):


  def setUp(self):
      curdir = os.path.dirname(os.path.realpath(__file__))
      BiomajConfig.load_config(os.path.join(curdir,'global.properties'))

      if not os.path.exists(os.path.join('/tmp/biomaj/config','alu.properties')):
        os.makedirs('/tmp/biomaj/config')

        shutil.copyfile(os.path.join(curdir,'alu.properties'),
                        os.path.join('/tmp/biomaj/config','alu.properties'))
      b = Bank('alu')
      b.delete()
      self.config = BiomajConfig('alu')
      data_dir = self.config.get('data.dir')
      lock_file = os.path.join(data_dir,'alu.lock')
      if os.path.exists(lock_file):
        os.remove(lock_file)

  # Should test this on local downloader, changing 1 file to force update,
  # else we would get same bank and there would be no update
  #def test_reuse_last_production(self):
  #    '''
  #    Get release
  #    '''
  #    b = Bank('alu')
  #    b.load_session(UpdateWorkflow.FLOW)
  #    res = b.update()
  #    b.update()
