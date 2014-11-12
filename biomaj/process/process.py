import logging
import os
import subprocess

class Process:
  '''
  Define a process to execute
  '''

  def __init__(self, name, exe, args, desc=None, proc_type=None, cluster=False, expand=True, bank_env=None, log_dir=None):
    '''
    Define one process

    :param name: name of the process (descriptive)
    :type name: str
    :param path: path to the executable (relative to process.dir or full path)
    :type path: str
    :param args: arguments
    :type args: str
    :param env: environnement variables to set
    :type env: list
    :param log_dir: directroy to place process stdout and stderr
    :type log_dir: str
    '''
    self.name = name
    self.exe = exe
    self.desc= desc
    self.args = args.split()
    self.bank_env = bank_env
    self.cluster = cluster
    self.type = proc_type
    self.expand = expand
    if log_dir is not None:
      self.output_file = os.path.join(log_dir,name+'.out')
      self.error_file = os.path.join(log_dir,name+'.err')
    else:
      self.output_file = name+'.out'
      self.error_file = name+'.err'

  def run(self, simulate=False):
    '''
    Execute process

    :param simulate: does not execute process
    :type simulate: bool
    :return: exit code of process
    '''
    args = [ self.exe ] + self.args
    logging.debug('PROCESS:EXEC:'+str(self.args))
    err= False
    if not simulate:
      logging.info('Run process '+self.name)
      with open(self.output_file,'w') as fout:
        with open(self.error_file,'w') as ferr:
          if self.expand:
            args = " ".join(args)
            proc = subprocess.Popen(args, stdout=fout, stderr=ferr, env=self.bank_env, shell=True)
          else:
            proc = subprocess.Popen(args, stdout=fout, stderr=ferr, env=self.bank_env, shell=False)
          proc.wait()
          if proc.returncode == 0:
            err = True
          fout.flush()
          ferr.flush()
    else:
      err = True
    logging.info('PROCESS:EXEC:' + self.name + ':' + str(err))

    return err
