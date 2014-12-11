import logging
import datetime
import os
import shutil
import tempfile
import re
import traceback

from biomaj.utils import Utils
from biomaj.download.ftp import FTPDownload
from biomaj.download.http import HTTPDownload
from biomaj.download.direct import MultiDownload, DirectFTPDownload, DirectHttpDownload
from biomaj.download.localcopy import LocalDownload
from biomaj.download.downloadthreads import DownloadThread

from biomaj.mongo_connector import MongoConnector
from biomaj.options import Options

from biomaj.process.processfactory import RemoveProcessFactory,PreProcessFactory,PostProcessFactory

class Workflow(object):
  '''
  Bank update workflow
  '''

  FLOW_INIT = 'init'
  FLOW_CHECK = 'check'
  FLOW_DEPENDS = 'depends'
  FLOW_PREPROCESS = 'preprocess'
  FLOW_RELEASE = 'release'
  FLOW_DOWNLOAD = 'download'
  FLOW_POSTPROCESS = 'postprocess'
  FLOW_REMOVEPROCESS = 'removeprocess'
  FLOW_PUBLISH = 'publish'
  FLOW_OVER = 'over'

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, bank, session=None):
    '''
    Instantiate a new workflow

    :param bank: bank on which to apply the workflow
    :type bank: :class:`biomaj.bank.Bank`
    '''
    self.bank = bank
    if session is None:
      self.session = bank.session
    else:
      self.session = session
    self.options = bank.options
    self.name = bank.name
    # Skip all remaining tasks, no need to update
    self.skip_all = False

    self.session._session['update'] = False
    self.session._session['remove'] = False

  def get_handler(self, protocol, server, remote_dir, list_file=[]):
    '''
    Get a protocol download handler
    '''
    downloader = None
    if protocol == 'ftp' or protocol == 'sftp':
      downloader = FTPDownload(protocol, server, remote_dir)
    if protocol == 'http':
      downloader = HTTPDownload(protocol, server, remote_dir, self.bank.config)
    if protocol == 'local':
      downloader = LocalDownload(remote_dir)
    if protocol == 'directftp':
      downloader = DirectFTPDownload('ftp', server, remote_dir, list_file)
    if protocol == 'directhttp':
      downloader = DirectHttpDownload('http', server, remote_dir, list_file)
    if downloader is not None:
      downloader.bank = self.bank.name
    return downloader


  def get_flow(self, task):
    for flow in Workflow.FLOW:
      if flow['name'] == task:
        return flow

  def start(self):
    '''
    Start the workflow
    '''
    logging.info('Workflow:Start')
    #print str(self.session._session['status'])
    for flow in self.session.flow:
      if self.skip_all:
        self.session._session['status'][flow['name']] = None
        self.session._session['status'][Workflow.FLOW_OVER] = True
        continue

      if self.options.get_option(Options.STOP_BEFORE) == flow['name']:
        self.wf_over()
        break
      # Always run INIT
      if flow['name'] == Workflow.FLOW_INIT or not self.session.get_status(flow['name']):
        logging.info('Workflow:Start:'+flow['name'])
        try:
          self.session._session['status'][flow['name']] = getattr(self, 'wf_'+flow['name'])()
        except Exception as e:
          self.session._session['status'][flow['name']] = False
          logging.error('Workflow:'+flow['name']+'Exception:'+str(e))
          logging.debug(traceback.format_exc())
          #print str(traceback.format_exc())
        finally:
          self.wf_progress(flow['name'], self.session._session['status'][flow['name']])
        if flow['name'] != Workflow.FLOW_OVER and not self.session.get_status(flow['name']):
            logging.error('Error during task '+flow['name'])
            if flow['name'] != Workflow.FLOW_INIT:
              self.wf_over()
            return False
        # Main task is over, execute sub tasks of main
        if not self.skip_all:
          for step in flow['steps']:
            res = getattr(self, 'wf_'+step)()
            if not res:
              logging.error('Error during '+flow['name']+' subtask: wf_' + step)
              self.wf_over()
              return False
      if self.options.get_option(Options.STOP_AFTER) == flow['name']:
        self.wf_over()
      #if self.options and 'stop_after' in self.options and self.options['stop_after'] == flow['name']:
        break
    self.wf_progress_end()
    return True

  def wf_progress_init(self):
    '''
    Set up new progress status
    '''
    status = {}
    status['log_file'] = {'status': self.session._session['log_file'], 'progress': 0}
    status['session'] = self.session._session['id']
    for flow in self.session.flow:
      if flow['name'] == 'download':
        status[flow['name']] = {'status': None, 'progress': 0, 'total': 0}
      elif flow['name'].endswith('process'):
        status[flow['name']] = {'status': None, 'progress': {}}
      elif flow['name'] == 'release':
        status[flow['name']] = {'status': None, 'progress': ''}
      else:
        status[flow['name']] = {'status': None, 'progress': 0}
    MongoConnector.banks.update({'name': self.name},{'$set': {'status': status}})

  def wf_progress_end(self):
    '''
    Reset progress status when workflow is over
    '''
    #MongoConnector.banks.update({'name': self.name},{'$set': {'status': None}})

  def wf_progress(self, task, status):
    '''
    Update bank status
    '''
    subtask = 'status.'+task+'.status'
    MongoConnector.banks.update({'name': self.name},{'$set': {subtask: status}})

  def wf_init(self):
    '''
    Initialize workflow
    '''
    logging.info('Workflow:wf_init')
    data_dir = self.session.config.get('data.dir')
    lock_file = os.path.join(data_dir,self.name+'.lock')
    if os.path.exists(lock_file):
      logging.error('Bank '+self.name+' is locked, a process may be in progress, else remove the lock file '+lock_file)
      #print 'Bank '+self.name+' is locked, a process may be in progress, else remove the lock file'
      return False
    f = open(lock_file, 'w')
    f.write('1')
    f.close()
    self.wf_progress_init()
    return True

  def wf_over(self):
    '''
    Workflow is over
    '''
    logging.info('Workflow:wf_over')
    data_dir = self.session.config.get('data.dir')
    lock_file = os.path.join(data_dir,self.name+'.lock')
    os.remove(lock_file)
    return True

class RemoveWorkflow(Workflow):
  '''
  Workflow to remove a bank instance
  '''

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'removeprocess', 'steps': []},
    { 'name': 'remove_release', 'steps': []},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, bank, session):
    '''
    Instantiate a new workflow

    :param bank: bank on which to apply the workflow
    :type bank: Bank
    :param session: session to remove
    :type session: :class:`biomaj.session.Session`
    '''
    Workflow.__init__(self, bank, session)
    logging.debug('New workflow')
    self.session._session['remove'] = True



  def wf_remove_release(self):
    logging.info('Workflow:wf_remove_release')
    if not self.session.get('update_session_id'):
      logging.error('Bug: update_session_id not set in session')
      return False

    if os.path.exists(self.session.get_full_release_directory()):
      shutil.rmtree(self.session.get_full_release_directory())
    return self.bank.remove_session(self.session.get('update_session_id'))

  def wf_removeprocess(self):
    logging.info('Workflow:wf_removepreprocess')
    metas = self.session._session['process']['removeprocess']
    pfactory = RemoveProcessFactory(self.bank, metas)
    res = pfactory.run()
    self.session._session['process']['removeprocess'] = pfactory.meta_status
    return res


class UpdateWorkflow(Workflow):
  '''
  Workflow for a bank update
  '''

  FLOW = [
    { 'name': 'init', 'steps': []},
    { 'name': 'check', 'steps': []},
    { 'name': 'depends', 'steps': []},
    { 'name': 'preprocess', 'steps': []},
    { 'name': 'release', 'steps': []},
    { 'name': 'download', 'steps': ['uncompress','copy']},
    { 'name': 'postprocess', 'steps': ['metadata', 'stats']},
    { 'name': 'publish', 'steps': ['clean_offline', 'delete_old']},
    { 'name': 'over', 'steps': []}
  ]

  def __init__(self, bank):
    '''
    Instantiate a new workflow

    :param bank: bank on which to apply the workflow
    :type bank: Bank
    '''
    Workflow.__init__(self, bank)
    logging.debug('New workflow')
    self.session._session['update'] = True

  def wf_init(self):
    err = super(UpdateWorkflow, self).wf_init()
    if not err:
      return False
    if self.options.get_option(Options.FROMSCRATCH):
      return self.wf_clean_offline()

    return True

  def wf_check(self):
    '''
    Basic checks
    '''
    logging.info('Workflow:wf_check')
    return True

  def wf_depends(self):
    '''
    Checks bank dependencies with other banks. If bank has dependencies, execute update on other banks first
    '''
    logging.info('Workflow:wf_depends')
    # Always rescan depends, there might be a new release
    self.session.set('depends', {})
    res = self.bank.update_dependencies()
    logging.info('Workflow:wf_depends:'+str(res))
    return res

  def wf_preprocess(self):
    '''
    Execute pre-processes
    '''
    logging.info('Workflow:wf_preprocess')
    metas = self.session._session['process']['preprocess']
    pfactory = PreProcessFactory(self.bank, metas)
    res = pfactory.run()
    self.session._session['process']['preprocess'] = pfactory.meta_status
    return res

  def wf_release(self):
    '''
    Find current release on remote
    '''
    logging.info('Workflow:wf_release')
    cf = self.session.config
    self.session.previous_release = self.session.get('release')
    logging.debug('Workflow:wf_release:previous_session:'+str(self.session.previous_release))
    if self.session.config.get('release.file') == '':
      logging.debug('Workflow:wf_release:norelease')
      self.session.set('release',None)
      return True
    else:
      protocol = cf.get('protocol')
      if cf.get('release.protocol') is not None:
        protocol = cf.get('release.protocol')
      server = cf.get('server')
      if cf.get('release.server') is not None:
        server = cf.get('release.server')
      remote_dir = cf.get('remote.dir')
      if cf.get('release.remote.dir') is not None:
        remote_dir = cf.get('release.remote.dir')
      release_downloader = self.get_handler(protocol,server,remote_dir)
      if cf.get('server.credentials') is not None:
        release_downloader.set_credentials(cf.get('server.credentials'))

      if release_downloader is None:
        logging.error('Protocol '+protocol+' not supported')
        return False

      (file_list, dir_list) = release_downloader.list()

      release_downloader.match([cf.get('release.file')], file_list, dir_list)
      if len(release_downloader.files_to_download) == 0:
        logging.error('release.file defined but does not match any file')
        return False
      if len(release_downloader.files_to_download) > 1:
        logging.error('release.file defined but matches multiple files')
        return False

      if cf.get('release.regexp') is None or not cf.get('release.regexp'):
        # Try to get from regexp in file name
        rel = re.search(cf.get('release.file'), release_downloader.files_to_download[0]['name'])
        if rel is None:
          logging.error('release.file defined but does not match any file')
          return False
        release = rel.group(1)
      else:
        # Download and extract
        tmp_dir = tempfile.mkdtemp('biomaj')
        rel_files = release_downloader.download(tmp_dir)
        rel_file = open(tmp_dir + '/' + rel_files[0]['name'])
        rel_content = rel_file.read()
        rel_file.close()
        shutil.rmtree(tmp_dir)
        rel = re.search(cf.get('release.regexp'), rel_content)
        if rel is None:
          logging.error('release.regexp defined but does not match any file content')
          return False
        release = rel.group(1)

      release_downloader.close()
      if release_downloader.error:
        logging.error('An error occured during download')
        return False

    self.session.set('release', release)

    MongoConnector.banks.update({'name': self.bank.name},{'$set': {'status.release.progress': str(release)}})

    # We restart from scratch, a directory with this release already exists
    if self.options.get_option(Options.FROMSCRATCH) and os.path.exists(self.session.get_full_release_directory()):
      index = 1
      while os.path.exists(self.session.get_full_release_directory()+'_'+str(index)):
        index += 1
      self.session.set('release', release+'_'+str(index))
    self.download_go_ahead = False
    if self.options.get_option(Options.FROM_TASK) == 'download':
      # We want to download again in same release, that's fine, we do not care it is the same release
      self.download_go_ahead = True
    if not self.download_go_ahead and self.session.previous_release == release:
      logging.debug('Workflow:wf_release:same_as_previous_session')
      return self.no_need_to_update()

    logging.info('Session:Release:'+self.session.get('release'))
    return True


  def no_need_to_update(self):
    '''
    Set status to over and update = False because there is not a need to update bank
    '''
    self.skip_all = True
    self.session._session['status'][Workflow.FLOW_OVER] = True
    self.session._session['update'] = False
    self.session.set('download_files',[])
    self.wf_over()
    return True

  def wf_download(self):
    '''
    Download remote files or use an available local copy from last production directory if possible.
    '''
    logging.info('Workflow:wf_download')
    flow = self.get_flow(Workflow.FLOW_DOWNLOAD)
    downloader = None
    cf = self.session.config


    if cf.get('protocol') == 'multi':
      '''
      Search for:
      protocol = multi
      remote.file.0.protocol = directftp
      remote.file.0.server = ftp.ncbi.org
      remote.file.0.path = /musmusculus/chr1/chr1.fa

      => http://ftp2.fr.debian.org/debian/README.html?key1=value&key2=value2
      remote.file.1.protocol = directhttp
      remote.file.1.server = ftp2.fr.debian.org
      remote.file.1.path = debian/README.html
      remote.file.1.method =  GET
      remote.file.1.params.keys = key1,key2
      remote.file.1.params.key1 = value1
      remote.file.1.params.key2 = value2

      => http://ftp2.fr.debian.org/debian/README.html
          #POST PARAMS:
            key1=value
            key2=value2
      remote.file.1.protocol = directhttp
      remote.file.1.server = ftp2.fr.debian.org
      remote.file.1.path = debian/README.html
      remote.file.1.method =  POST
      remote.file.1.params.keys = key1,key2
      remote.file.1.params.key1 = value1
      remote.file.1.params.key2 = value2

      ......
      '''
      downloader = MultiDownload()
      downloaders = []
      # Creates multiple downloaders
      i = 0
      rfile = cf.get('remote.file.'+str(i)+'.path')
      while(rfile is not None):
        if cf.get('remote.file.'+str(i)+'.protocol') is not None:
          protocol = cf.get('remote.file.'+str(i)+'.protocol')
        else:
          protocol = cf.get('protocol')
        if cf.get('remote.file.'+str(i)+'.server') is not None:
          server = cf.get('remote.file.'+str(i)+'.server')
        else:
          server = cf.get('server')
        subdownloader = self.get_handler(protocol,server,'', [cf.get('remote.file.'+str(i)+'.path')])
        if cf.get('remote.file.'+str(i)+'.credentials') is not None:
          credentials = cf.get('remote.file.'+str(i)+'.credentials')
        else:
          credentials = cf.get('server.credentials')
        if credentials is not None:
          subdownloader.set_credentials(credentials)
        if protocol == 'directhttp':
          subdownloader.method = cf.get('remote.file.'+str(i)+'.method')
          if subdownloader.method is None:
            subdownloader.method = 'GET'
          if cf.get('remote.file.'+str(i)+'.name'):
            subdownloader.save_as = cf.get('remote.file.'+str(i)+'.name')
          else:
            subdownloader.save_as = cf.get('remote.file.'+str(i)+'.path')
          if cf.get('remote.file.'+str(i)+'.method'):
            subdownloader.method = cf.get('remote.file.'+str(i)+'.method').strip().upper()
          subdownloader.params = {}
          keys = cf.get('remote.file.'+str(i)+'.params.keys')
          if keys is not None:
            keys = keys.split(',')
            for key in keys:
              param = cf.get('remote.file.'+str(i)+'.params.'+key.strip())
              subdownloader.param[key.strip()] = param.strip()
        downloaders.append(subdownloader)
        i += 1
        rfile = cf.get('remote.file.'+str(i)+'.path')
      downloader.add_downloaders(downloaders)

    else:
      '''
      Simple case, one downloader with regexp
      '''
      downloader = self.get_handler(cf.get('protocol'),cf.get('server'),cf.get('remote.dir'))

    if downloader is None:
      logging.error('Protocol '+cf.get('protocol')+' not supported')
      return False

    (file_list, dir_list) = downloader.list()

    downloader.match(cf.get('remote.files').split(), file_list, dir_list)

    self.session.set('download_files',downloader.files_to_download)
    if self.session.get('release') is None:
        # Not defined, or could not get it ealier
        # Set release to most recent file to download
        release_dict = Utils.get_more_recent_file(downloader.files_to_download)
        release = str(release_dict['year']) + '-' + str(release_dict['month']) + '-' + str(release_dict['day'])
        self.session.set('release', release)
        # We restart from scratch, a directory with this release already exists
        if self.options.get_option(Options.FROMSCRATCH) and os.path.exists(self.session.get_full_release_directory()):
          index = 1
          while os.path.exists(self.session.get_full_release_directory()+'_'+str(index)):
            index += 1
          self.session.set('release', release+'_'+str(index))
          release = release+'_'+str(index)
        logging.debug('Workflow:wf_release:release:'+release)
        MongoConnector.banks.update({'name': self.bank.name},{'$set': {'status.release.progress': str(release)}})
        self.download_go_ahead = False
        if self.options.get_option(Options.FROM_TASK) == 'download':
          # We want to download again in same release, that's fine, we do not care it is the same release
          self.download_go_ahead = True
        if not self.download_go_ahead and self.session.previous_release == release:
          logging.debug('Workflow:wf_release:same_as_previous_session')
          return self.no_need_to_update()

    self.banks = MongoConnector.banks
    self.bank.bank = self.banks.find_one({'name': self.name},{ 'production': 1})

    nb_prod_dir = len(self.bank.bank['production'])
    offline_dir = self.session.get_offline_directory()

    copied_files = []

    # Check if already in offlinedir
    keep_files = []
    if os.path.exists(offline_dir):
      for file_to_download in downloader.files_to_download:
        # If file is in offline dir and has same date and size, do not download again
        if os.path.exists(offline_dir + '/' + file_to_download['name']):
          file_stat = os.stat(offline_dir + '/' + file_to_download['name'])
          f_stat = datetime.datetime.fromtimestamp(os.path.getmtime(offline_dir + '/' + file_to_download['name']))
          year = str(f_stat.year)
          month = str(f_stat.month)
          day = str(f_stat.day)
          if file_stat.ST_SIZE != file_to_download['size'] or \
             year != file_to_download['year'] or \
             month != file_to_download['month'] or \
             day != file_to_download['day']:
            keep_files.append(file_to_download)
          else:
            logging.debug('Workflow:wf_download:offline:'+file_to_download['name'])
        else:
          keep_files.append(file_to_download)
      downloader.files_to_download = keep_files

    self.download_go_ahead = False
    if self.options.get_option(Options.FROM_TASK) == 'download':
      # We want to download again in same release, that's fine, we do not care it is the same release
      self.download_go_ahead = True

    if not self.options.get_option(Options.FROMSCRATCH) and not self.download_go_ahead and nb_prod_dir > 0:
      for prod in self.bank.bank['production']:
        if self.session.get('release') == prod['release']:
          logging.debug('Workflow:wf_release:same_as_previous_production_dir')
          return self.no_need_to_update()


      # Get last production
      last_production = self.bank.bank['production'][nb_prod_dir-1]
      # Get session corresponding to production directory
      last_production_session = self.banks.find_one({'name': self.name, 'sessions.id': last_production['session']},{ 'sessions.$': 1})
      last_production_dir = os.path.join(last_production['data_dir'],cf.get('dir.version'),last_production['release'])
      # Checks if some files can be copied instead of downloaded
      downloader.download_or_copy(last_production_session['sessions'][0]['files'],last_production_dir)
      if len(downloader.files_to_download) == 0:
        return self.no_need_to_update()

      #release_dir = os.path.join(self.session.config.get('data.dir'),
      #              self.session.config.get('dir.version'),
      #              self.session.get_release_directory())
      logging.debug('Workflow:wf_download:Copy files from '+last_production_dir)
      copied_files = downloader.files_to_copy
      Utils.copy_files(downloader.files_to_copy, offline_dir)


    downloader.close()

    DownloadThread.NB_THREAD = int(self.session.config.get('files.num.threads'))

    if cf.get('protocol') == 'multi':
      thlist = DownloadThread.get_threads_multi(downloader.downloaders, offline_dir)
    else:
      thlist = DownloadThread.get_threads(downloader, offline_dir)

    for th in thlist:
      th.start()
    for th in thlist:
      th.join()
    is_error = False
    for th in thlist:
      if th.error:
        is_error = True
        downloader.error = True
        break
    self.downloaded_files = downloader.files_to_download + copied_files
    #self.downloaded_files = downloader.download(offline_dir) + copied_files

    #downloader.close()

    if downloader.error:
      logging.error('An error occured during download')
      return False

    return True

  def wf_uncompress(self):
    '''
    Uncompress files if archives and no.extract = false
    '''
    logging.info('Workflow:wf_uncompress')
    no_extract = self.session.config.get('no.extract')
    if no_extract is None or no_extract == 'false':
      for file in self.downloaded_files:
        Utils.uncompress(self.session.get_offline_directory() + '/' + file['name'])
    return True

  def wf_copy(self):
    '''
    Copy files from offline directory to release directory
    '''
    logging.info('Workflow:wf_copy')
    from_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('offline.dir.name'))
    regexp = self.session.config.get('local.files').split()
    to_dir = os.path.join(self.session.config.get('data.dir'),
                  self.session.config.get('dir.version'),
                  self.session.get_release_directory(), 'flat')

    local_files = Utils.copy_files_with_regexp(from_dir,to_dir,regexp, True)
    self.session._session['files'] = local_files
    if len(self.session._session['files']) == 0:
      logging.error('Workflow:wf_copy:No file match in offline dir')
      return False
    return True

  def wf_metadata(self):
    '''
    Update metadata with info gathered from processes
    '''
    logging.info('Workflow:wf_metadata')
    self.bank.session.set('formats', {})
    per_process_meta_data = self.session.get('per_process_metadata')
    for proc in per_process_meta_data.keys():
      for meta_data in per_process_meta_data[proc].keys():
        session_formats = self.bank.session.get('formats')
        if meta_data not in session_formats:
          #session_formats[meta_data] = [meta_thread.meta_data[meta_data]]
          session_formats[meta_data] = per_process_meta_data[proc][meta_data]
        else:
          #session_formats[meta_data].append(meta_thread.meta_data[meta_data])
          session_formats[meta_data] += per_process_meta_data[proc][meta_data]
    return True

  def wf_stats(self):
    '''
    Get some stats from current release data dir
    '''
    logging.info('Workflow:wf_stats')
    do_stats = self.bank.config.get('data.stats')
    if do_stats is None or do_stats == '0':
      self.session.set('fullsize', 0)
      return True
    prod_dir = self.session.get_full_release_directory()
    dir_size = Utils.get_folder_size(prod_dir)
    self.session.set('fullsize', dir_size)
    return True

  def wf_postprocess(self):
    '''
    Execute post processes
    '''

    # Creates a temporary symlink future_release to keep compatibility if process
    # tries to access dir with this name
    future_link = os.path.join(self.bank.config.get('data.dir'),
                                self.bank.config.get('dir.version'),
                                'future_release')
    prod_dir = self.session.get_full_release_directory()
    to_dir = os.path.join(self.bank.config.get('data.dir'),
                  self.bank.config.get('dir.version'))

    if os.path.lexists(future_link):
      os.remove(future_link)
    os.chdir(to_dir)
    os.symlink(self.session.get_release_directory(),'future_release')

    logging.info('Workflow:wf_postprocess')
    blocks = self.session._session['process']['postprocess']
    pfactory = PostProcessFactory(self.bank, blocks)
    res = pfactory.run()
    self.session._session['process']['postprocess'] = pfactory.blocks

    # In any way, delete symlink
    if os.path.lexists(future_link):
      os.remove(future_link)

    return res

  def wf_publish(self):
    '''
    Add *current* symlink to this release
    '''

    if not self.options.get_option(Options.PUBLISH):
      logging.info('Workflow:wf_publish:no')
      return True
    logging.info('Workflow:wf_publish')
    self.bank.publish()
    return True

  def wf_clean_offline(self):
    '''
    Clean offline directory
    '''
    logging.info('Workflow:wf_clean_offline')
    if os.path.exists(self.session.get_offline_directory()):
      shutil.rmtree(self.session.get_offline_directory())
    return True

  def wf_clean_old_sessions(self):
    '''
    Delete old sessions not related to a production directory or last run
    '''
    logging.info('Workflow:wf_clean_old_sessions')
    self.bank.clean_old_sessions()
    return True

  def wf_delete_old(self):
    '''
    Delete old production dirs
    '''
    logging.info('Workflow:wf_delete_old')
    keep = int(self.session.config.get('keep.old.version'))
    # Current production dir is not yet in list
    nb_prod = len(self.bank.bank['production'])
    # save session during delete workflow
    keep_session = self.bank.session

    if nb_prod > keep:
      for prod in self.bank.bank['production']:
        if 'freeze' in prod and prod['freeze']:
          continue
        if nb_prod - keep > 0:
          nb_prod -= 1
          session = self.bank.get_new_session(RemoveWorkflow.FLOW)
          # Delete init and over because we are already in a run
          i_init = -1
          i_over = -1
          for i in range(0,len(session.flow)):
            if session.flow[i]['name'] == 'init':
              i_init = i
          if i_init >= 0:
            del session.flow[i_init]
          for i in range(0,len(session.flow)):
            if session.flow[i]['name'] == 'over':
              i_over = i
          if i_over >= 0:
            del session.flow[i_over]

          session.set('action', 'remove')
          session.set('release', prod['release'])
          session.set('update_session_id', prod['session'])
          res = self.bank.start_remove(session)
          if not res:
            logging.error('Workflow:wf_delete_old:ErrorDelete:'+prod['release'])
        else:
          break
    # Set session back
    self.bank.session  = keep_session

    return True
