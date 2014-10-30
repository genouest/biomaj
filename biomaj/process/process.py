

class Process:
  '''
  Define a process to execute
  '''

  def __init__(self, name, path, args, env=None):
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
    '''
    self.name = name
    self.path = path
    self.args = args
    self.env = env

  def run(self):
    pass
