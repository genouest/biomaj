from nose.tools import *

import shutil
import os

from biomaj.bank import Bank
from biomaj.session import Session
from biomaj.workflow import Workflow

import unittest

class TestBiomaj(unittest.TestCase):


  def setUp(self):
      curdir = os.path.dirname(os.path.realpath(__file__))
      Bank.load_config(os.path.join(curdir,'global.properties'))

      if not os.path.exists(os.path.join('/tmp/biomaj/config','alu.properties')):
        os.makedirs('/tmp/biomaj/config')

        shutil.copyfile(os.path.join(curdir,'alu.properties'),
                        os.path.join('/tmp/biomaj/config','alu.properties'))
      b = Bank('alu')
      b.delete()



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
        s = Session(Bank.config, b.config_bank)
        s._session['status'][Workflow.FLOW_INIT] = True
        b.session = s
        b.save_session()

      b = Bank('alu')
      b.load_session()
      self.assertTrue(b.session.get_status(Workflow.FLOW_INIT))
