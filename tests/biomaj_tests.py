import json
import shutil
import os
import tempfile
import logging
import copy
import stat
import time
import pytest

from mock import patch

from optparse import OptionParser


from biomaj.bank import Bank
from biomaj.session import Session
from biomaj.workflow import Workflow
from biomaj.workflow import UpdateWorkflow
from biomaj.workflow import ReleaseCheckWorkflow
from biomaj_core.utils import Utils
from biomaj_core.config import BiomajConfig
from biomaj.process.processfactory import PostProcessFactory
from biomaj.process.processfactory import PreProcessFactory
from biomaj.process.processfactory import RemoveProcessFactory
from biomaj_user.user import BmajUser
from biomaj_core.bmajindex import BmajIndex


class UtilsForTest():
  """
  Copy properties files to a temp directory and update properties to
  use a temp directory
  """

  def __init__(self):
    """
    Setup the temp dirs and files.
    """
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
    """
    Deletes temp directory
    """
    shutil.rmtree(self.test_dir)

  def __copy_test_bank_properties(self):
    if self.bank_properties is not None:
      return
    self.bank_properties = ['alu', 'local', 'testhttp','directhttp',
                            'alu_list_error']
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
    properties = ['multi.properties', 'computederror.properties',
                  'error.properties', 'local.properties',
                  'localprocess.properties', 'testhttp.properties',
                  'computed.properties', 'computed2.properties',
                  'sub1.properties', 'sub2.properties']
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


class TestBiomajSetup():

  def setup_method(self, m):
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

  def teardown_method(self, m):
    data_dir = self.config.get('data.dir')
    lock_file = os.path.join(data_dir,'alu.lock')
    if os.path.exists(lock_file):
      os.remove(lock_file)
    self.utils.clean()

  def test_new_bank(self):
    """
    Checks bank init
    """
    b = Bank('alu')

  def test_new_session(self):
    """
    Checks an empty session is created
    """
    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    for key in b.session._session['status'].keys():
      assert not(b.session.get_status(key))

  def test_session_reload_notover(self):
    """
    Checks a session is used if present
    """
    b = Bank('alu')
    for i in range(1, 5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()

    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    assert (b.session.get_status(Workflow.FLOW_INIT))

  def test_clean_old_sessions(self):
    """
    Checks a session is used if present
    """
    b = Bank('local')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()
    b2 = Bank('local')
    b2.update()
    b2.clean_old_sessions()
    assert (len(b2.bank['sessions']) == 1)

  def test_session_reload_over(self):
    """
    Checks a session if is not over
    """
    b = Bank('alu')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      s._session['status'][Workflow.FLOW_OVER] = True
      b.session = s
      b.save_session()

    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    assert not (b.session.get_status(Workflow.FLOW_INIT))

  def test_bank_list(self):
    b1 = Bank('alu')
    b2 = Bank('local')
    banks = Bank.list()
    assert (len(banks) == 2)

  @pytest.mark.skipif(
  os.environ.get('NETWORK', 1) == '0',
  reason='network tests disabled'
  )
  def test_get_release(self):
    """
    Get release
    """
    b = Bank('alu')
    b.load_session(UpdateWorkflow.FLOW)
    res = b.update()
    assert (b.session.get('update'))
    assert (res)
    assert (b.session._session['release'] is not None)

  @pytest.mark.skipif(
  os.environ.get('NETWORK', 1) == '0',
  reason='network tests disabled'
  )
  def test_remove_session(self):
    b = Bank('alu')
    for i in range(1,5):
      s = Session('alu', self.config, UpdateWorkflow.FLOW)
      s._session['status'][Workflow.FLOW_INIT] = True
      b.session = s
      b.save_session()
    assert (len(b.bank['sessions'])==4)
    b.remove_session(b.session.get('id'))
    assert (len(b.bank['sessions'])==3)

  def test_postprocesses_setup(self):
    b = Bank('localprocess')
    pfactory = PostProcessFactory(b)
    pfactory.run(True)
    assert (len(pfactory.threads_tasks[0])==2)
    assert (len(pfactory.threads_tasks[1])==1)

  def test_postprocesses_exec_again(self):
    """
    Execute once, set a status to false, check that False processes are executed
    """
    b = Bank('localprocess')
    pfactory = PostProcessFactory(b)
    pfactory.run()
    assert (pfactory.blocks['BLOCK1']['META0']['PROC0'])
    assert (pfactory.blocks['BLOCK2']['META1']['PROC1'])
    assert (pfactory.blocks['BLOCK2']['META1']['PROC2'])
    blocks = copy.deepcopy(pfactory.blocks)
    blocks['BLOCK2']['META1']['PROC2'] = False
    pfactory2 = PostProcessFactory(b, blocks)
    pfactory2.run()
    assert (pfactory2.blocks['BLOCK2']['META1']['PROC2'])

  def test_preprocesses(self):
    b = Bank('localprocess')
    pfactory = PreProcessFactory(b)
    pfactory.run()
    assert (pfactory.meta_status['META0']['PROC0'])

  def test_removeprocesses(self):
    b = Bank('localprocess')
    pfactory = RemoveProcessFactory(b)
    pfactory.run()
    assert (pfactory.meta_status['META0']['PROC0'])

  def test_dependencies_list(self):
    b = Bank('computed')
    deps = b.get_dependencies()
    assert (len(deps)==2)

class TestBiomajFunctional():

  # Banks used in tests
  BANKS = ['local', 'alu_list_error']

  def setup_method(self, m):
    self.utils = UtilsForTest()
    BiomajConfig.load_config(self.utils.global_properties, allow_user_config=False)

    # Clean banks used in tests
    for bank_name in self.BANKS:
      # Delete all releases
      b = Bank(bank_name)
      b.banks.remove({})
      # Delete lock files
      config = BiomajConfig(bank_name)
      data_dir = config.get('data.dir')
      lock_file = os.path.join(data_dir, 'local.lock')
      if os.path.exists(lock_file):
        os.remove(lock_file)

  def teardown_method(self, m):
    # Delete lock files
    for bank_name in self.BANKS:
      config = BiomajConfig(bank_name)
      data_dir = config.get('data.dir')
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
    assert (b.session.get('release') == '100')

  def test_remoterelease_check(self):
      b = Bank('local')
      b.load_session(ReleaseCheckWorkflow.FLOW)
      b.session.config.set('release.file', 'test_(\d+)\.txt')
      b.session.config.set('release.regexp', '')
      workflow = ReleaseCheckWorkflow(b)
      res = workflow.start()
      remoterelease = b.session.get('remoterelease')
      assert (remoterelease == '100')

  def test_extract_release_from_file_content(self):
    b = Bank('local')
    b.load_session(UpdateWorkflow.FLOW)
    b.session.config.set('release.file', 'test_100\.txt')
    b.session.config.set('release.regexp', 'Release\s*(\d+)')
    w = UpdateWorkflow(b)
    w.wf_release()
    assert (b.session.get('release') == '103')

  def test_publish(self):
    """
    Update a bank, then publish it
    """
    b = Bank('local')
    b.update()
    current_link = os.path.join(b.config.get('data.dir'),
                                b.config.get('dir.version'),
                                'current')
    assert not (os.path.exists(current_link))
    assert (b.bank['current'] is None)
    b.publish()
    assert (os.path.exists(current_link))
    assert (b.bank['current'] == b.session._session['id'])

  # Should test this on local downloader, changing 1 file to force update,
  # else we would get same bank and there would be no update
  def test_no_update(self):
      """
      Try updating twice, at second time, bank should not be updated
      """
      b = Bank('local')
      b.update()
      assert (b.session.get('update'))
      b.update()
      assert not (b.session.get('update'))
      assert not (b.session.get_status(Workflow.FLOW_POSTPROCESS))

  def test_download_from_list(self):
      """
      Use remote.list to define a list of files to download
      """
      b = Bank('local')
      fd, file_path = tempfile.mkstemp()
      try:
          b.config.set('remote.list', file_path)
          with os.fdopen(fd, 'w') as tmp:
              tmp.write('[{"name": "test_100.txt", "root": "' + b.config.get('remote.dir') + '"}]')
          b.update()
          assert (b.session.get('update'))
      finally:
          #os.remove(file_path)
          print(file_path)

  def test_release_control(self):
    """
    Try updating twice, at second time, modify one file (same date),
     bank should update
    """
    b = Bank('local')
    b.update()
    b.session.config.set('keep.old.version', '3')
    assert (b.session.get('update'))
    remote_file = b.session.config.get('remote.dir') + 'test2.fasta'
    os.utime(remote_file, None)
    # Update test2.fasta and set release.control
    b.session.config.set('release.control', 'true')
    b.update()
    assert (b.session.get('update'))
    b.update()
    assert not (b.session.get('update'))
    b.session.config.set('copy.skip', '1')
    b.session.config.set('remote.files', '^test2.fasta')
    b.update()
    assert (b.session.get('update'))

  def test_update_hardlinks(self):
    """
    Update a bank twice with hard links. Files copied from previous release
    must be links.
    """
    b = Bank('local')
    b.config.set('keep.old.version', '3')
    b.config.set('use_hardlinks', '1')
    # Create a file in bank dir (which is the source dir) so we can manipulate
    # it. The pattern is taken into account by the bank configuration.
    # Note that this file is created in the source tree so we remove it after
    # or if this test fails in between.
    tmp_remote_file = b.config.get('remote.dir') + 'test.safe_to_del'
    if os.path.exists(tmp_remote_file):
        os.remove(tmp_remote_file)
    open(tmp_remote_file, "w")
    # First update
    b.update()
    assert (b.session.get('update'))
    old_release = b.session.get_full_release_directory()
    # Touch tmp_remote_file to force update. We set the date to tomorrow so we
    # are sure that a new release will be detected.
    tomorrow = time.time() + 3660 * 24  # 3660s for safety (leap second, etc.)
    os.utime(tmp_remote_file, (tomorrow, tomorrow))
    # Second update
    try:
        b.update()
        assert (b.session.get('update'))
        new_release = b.session.get_full_release_directory()
        # Test that files in both releases are links to the the same file.
        # We can't use tmp_remote_file because it's the source of update and we
        # can't use test.fasta.gz because it is uncompressed and then not the
        # same file.
        for f in ['test2.fasta', 'test_100.txt']:
             file_old_release = os.path.join(old_release, 'flat', f)
             file_new_release = os.path.join(new_release, 'flat', f)
             try:
                 assert (os.path.samefile(file_old_release, file_new_release))
             except AssertionError:
                 msg = "In %s: copy worked but hardlinks were not used." % self.id()
                 logging.info(msg)
        # Test that no links are done for tmp_remote_file
        file_old_release = os.path.join(old_release, 'flat', 'test.safe_to_del')
        file_new_release = os.path.join(new_release, 'flat', 'test.safe_to_del')
        assert not (os.path.samefile(file_old_release, file_new_release))
    except Exception:
        raise
    finally:
        # Remove file
        if os.path.exists(tmp_remote_file):
            os.remove(tmp_remote_file)

  def test_fromscratch_update(self):
      """
      Try updating twice, at second time, bank should  be updated (force with fromscratc)
      """
      b = Bank('local')
      b.update()
      assert (b.session.get('update'))
      sess = b.session.get('release')
      b.options.fromscratch = True
      b.update()
      assert (b.session.get('update'))
      assert (b.session.get('release') == sess+'__1')


  def test_fromscratch_update_with_release(self):
      """
      Try updating twice, at second time, bank should  be updated (force with fromscratch)

      Use case with release defined in release file
      """
      b = Bank('local')
      b.load_session(UpdateWorkflow.FLOW)
      b.session.config.set('release.file', 'test_(\d+)\.txt')
      b.session.config.set('release.regexp', '')
      w = UpdateWorkflow(b)
      w.wf_release()
      assert (b.session.get('release') == '100')
      os.makedirs(b.session.get_full_release_directory())
      w = UpdateWorkflow(b)
      # Reset release
      b.session.set('release', None)
      w.options.fromscratch = True
      w.wf_release()
      assert (b.session.get('release') == '100__1')


  def test_mix_stop_from_task(self):
      """
      Get a first release, then fromscratch --stop-after, then restart from-task
      """
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      assert (b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      assert (b3.session.get('release') == rel+'__1')
      assert (res)

  def test_mix_stop_from_task2(self):
      """
      Get a first release, then fromscratch --stop-after, then restart from-task
      """
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      assert (b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      b2.options.from_task = 'download'
      assert (b3.session.get('release') == rel+'__1')
      assert (res)

  def test_mix_stop_from_task3(self):
      """
      Get a first release, then fromscratch --stop-after, then restart from-task
      """
      b = Bank('local')
      b.update()
      rel = b.session.get('release')
      b2 = Bank('local')
      b2.options.stop_after = 'download'
      b2.options.fromscratch = True
      res = b2.update()
      assert (b2.session.get('release') == rel+'__1')
      b3 = Bank('local')
      res = b3.update()
      b2.options.from_task = 'postprocess'
      assert (b3.session.get('release') == rel+'__1')
      assert (res)

  def test_mix_stop_from_task4(self):
      """
      Get a first release, then fromscratch --stop-after, then restart from-task
      """
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
      assert not (res)

  def test_delete_old_dirs(self):
      """
      Try updating 3 times, oldest dir should be removed
      """
      b = Bank('local')
      b.removeAll(True)
      b = Bank('local')
      b.update()
      assert (b.session.get('update'))
      b.options.fromscratch = True
      b.update()
      assert (b.session.get('update'))
      assert (len(b.bank['production']) == 2)
      b.update()
      assert (b.session.get('update'))
      # one new dir, but olders must be deleted
      assert (len(b.bank['production']) == 2)

  def test_delete_old_dirs_with_freeze(self):
      """
      Try updating 3 times, oldest dir should be removed but not freezed releases
      """
      b = Bank('local')
      b.removeAll(True)
      b = Bank('local')
      b.update()
      b.freeze(b.session.get('release'))
      assert (b.session.get('update'))
      b.options.fromscratch = True
      b.update()
      b.freeze(b.session.get('release'))
      assert (b.session.get('update'))
      assert (len(b.bank['production']) == 2)
      b.update()
      assert (b.session.get('update'))
      # one new dir, but olders must be deleted
      assert (len(b.bank['production']) == 3)

  def test_removeAll(self):
    b = Bank('local')
    b.update()
    b.removeAll()
    assert not (os.path.exists(b.get_data_dir()))
    bdb = b.banks.find_one({'name': b.name})
    assert (bdb is None)

  def test_remove(self):
    """
    test removal of a production dir
    """
    b = Bank('local')
    b.update()
    assert (os.path.exists(b.session.get_full_release_directory()))
    assert (len(b.bank['production'])==1)
    b.remove(b.session.get('release'))
    assert not (os.path.exists(b.session.get_full_release_directory()))
    b = Bank('local')
    assert (len(b.bank['production'])==0)

  def test_update_stop_after(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    assert (b.session.get_status('download'))
    assert not (b.session.get_status('postprocess'))

  def test_update_stop_before(self):
    b = Bank('local')
    b.options.stop_before = 'postprocess'
    b.update()
    assert (b.session.get_status('download'))
    assert not (b.session.get_status('postprocess'))

  def test_reupdate_from_task(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    assert not (b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    b2.update()
    assert (b2.session.get_status('postprocess'))
    assert (b.session.get_full_release_directory() == b2.session.get_full_release_directory())

  def test_reupdate_from_task_error(self):
    b = Bank('local')
    b.options.stop_after = 'check'
    b.update()
    assert not (b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    res = b2.update()
    assert not (res)

  def test_reupdate_from_task_wrong_release(self):
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    assert not (b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = 'wrongrelease'
    res = b2.update()
    assert not (res)

  def test_postprocesses_restart_from_proc(self):
    b = Bank('localprocess')
    b.update()
    proc1file = os.path.join(b.session.get_full_release_directory(),'proc1.txt')
    proc2file = os.path.join(b.session.get_full_release_directory(),'proc2.txt')
    assert (os.path.exists(proc1file))
    assert (os.path.exists(proc2file))
    os.remove(proc1file)
    os.remove(proc2file)
    # Restart from postprocess, reexecute all processes
    b2 = Bank('localprocess')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    b2.update()
    assert (os.path.exists(proc1file))
    assert (os.path.exists(proc2file))
    os.remove(proc1file)
    os.remove(proc2file)
    # Restart from postprocess, but at process PROC2 and following
    b3 = Bank('localprocess')
    b3.options.from_task = 'postprocess'
    b3.options.process = 'PROC2'
    b3.options.release = b.session.get('release')
    b3.update()
    #assert not (os.path.exists(proc1file))
    assert (os.path.exists(proc2file))

  def test_postprocess_wrong_process_name(self):
    """If a wrong process name is given, update returns False and prints an error message"""
    b = Bank('local')
    b.options.stop_after = 'download'
    b.update()
    assert not (b.session.get_status('postprocess'))
    b2 = Bank('local')
    b2.options.from_task = 'postprocess'
    b2.options.release = b.session.get('release')
    b2.options.process = 'fake'
    assert not (b2.update())
    assert not (b2.session.get_status('postprocess'))
    assert (b.session.get_full_release_directory() == b2.session.get_full_release_directory())

  def test_computed(self):
    b = Bank('computed')
    res = b.update(True)
    assert (res)
    assert (os.path.exists(b.session.get_full_release_directory()+'/sub1/flat/test_100.txt'))
    assert (b.session.get('update'))
    # Check that, with depends non updated, bank is not updated itself
    nextb = Bank('computed')
    res = nextb.update(True)
    assert not (nextb.session.get('update'))

  def test_computed_nofile(self):
    b = Bank('computed2')
    b.load_session(UpdateWorkflow.FLOW)
    b.session.config.set('protocol', 'none')
    b.session.config.set('sub1.files.move', 'flat/test_.*')
    res = b.update(True)
    assert (res)
    assert (os.path.exists(b.session.get_full_release_directory()+'/sub1/flat/test_100.txt'))

  def test_computed_ref_release(self):
    b = Bank('computed2')
    res = b.update(True)
    b2 = Bank('sub1')
    b2release = b2.bank['production'][len(b2.bank['production'])-1]['release']
    brelease = b.bank['production'][len(b.bank['production'])-1]['release']
    assert (res)
    assert (brelease == b2release)

  def test_computed_ref_release(self):
    b = Bank('computed2')
    res = b.update(True)
    assert (b.session.get('update'))
    b2 = Bank('computed2')
    res = b2.update(True)
    assert not (b2.session.get('update'))

  def test_computederror(self):
    b = Bank('computederror')
    res = b.update(True)
    assert not (res)
    assert (b.session._session['depends']['sub2'])
    assert not (b.session._session['depends']['error'])

  @pytest.mark.skipif(
    os.environ.get('NETWORK', 1) == '0',
    reason='network tests disabled'
  )
  def test_directhttp_release(self):
      b = Bank('directhttp')
      res = b.update()
      assert (b.session.get('update'))
      assert (os.path.exists(b.session.get_full_release_directory()+'/flat/debian/README.html'))
      # print str(b.session.get('release'))
      # print str(b.session.get('remoterelease'))

  @pytest.mark.skipif(
  os.environ.get('NETWORK', 1) == '0',
  reason='network tests disabled'
  )
  def test_multi(self):
    b = Bank('multi')
    res = b.update()
    assert (res)
    with open(os.path.join(b.session.get_full_release_directory(),'flat/test1.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      assert (my_json['args']['key1'] == 'value1')
    with open(os.path.join(b.session.get_full_release_directory(),'flat/test2.json'), 'r') as content_file:
      content = content_file.read()
      my_json = json.loads(content)
      assert (my_json['form']['key1'] == 'value1')

  def test_freeze(self):
    b = Bank('local')
    b.update()
    rel = b.session.get('release')
    b.freeze(rel)
    prod = b.get_production(rel)
    assert (prod['freeze'] == True)
    res = b.remove(rel)
    assert (res == False)
    b.unfreeze(rel)
    prod = b.get_production(rel)
    assert (prod['freeze'] == False)
    res = b.remove(rel)
    assert (res == True)

  def test_stats(self):
    b = Bank('local')
    b.update()
    rel = b.session.get('release')
    stats = Bank.get_banks_disk_usage()
    assert (stats[0]['size']>0)
    for release in stats[0]['releases']:
      if release['name'] == rel:
        assert (release['size']>0)

  def test_processes_meta_data(self):
    b = Bank('localprocess')
    b.update()
    formats = b.session.get('formats')
    assert (len(formats['blast'])==2)
    assert (len(formats['test'][0]['files'])==3)

  def test_search(self):
    b = Bank('localprocess')
    b.update()
    search_res = Bank.search(['blast'],[])
    assert (len(search_res)==1)
    search_res = Bank.search([],['nucleic'])
    assert (len(search_res)==1)
    search_res = Bank.search(['blast'],['nucleic'])
    assert (len(search_res)==1)
    search_res = Bank.search(['blast'],['proteic'])
    assert (len(search_res)==0)

  def test_owner(self):
    """
    test ACL with owner
    """
    b = Bank('local')
    res = b.update()
    assert (res)
    b.set_owner('sample')
    b2 = Bank('local')
    try:
      res = b2.update()
      self.fail('not owner, should not be allowed')
    except Exception as e:
      pass

  @pytest.mark.skipif(
  os.environ.get('NETWORK', 1) == '0',
  reason='network tests disabled'
  )
  def test_bank_list_error(self):
    b = Bank('alu_list_error')
    res = b.update()
    assert not (res)
