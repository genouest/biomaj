

class ProcessFactory:
  '''
  Manage process execution
  '''

  def __init__(self):
    pass


class PreProcessFactory(ProcessFactory):
  '''
  Manage preprocesses
  '''

  def __init__(self):
    ProcessFactory.__init__(self)


class PostProcessFactory(ProcessFactory):
  '''
  Manage postprocesses
  '''

  def __init__(self):
    ProcessFactory.__init__(self)
