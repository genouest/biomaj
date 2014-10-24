

class Options:
  '''
  Available options
  '''

  def __init__(self, options={}):
    if options is None:
      self.options = {}
    else:
      self.options = options

  def get_option(self, option):
    '''
    Gets an option if present, else return None
    '''
    if option in self.options:
      return self.options[option]
    return None

  NO_PUBLISH = 'no_publish'
  STOP_BEFORE = 'stop_before'
  STOP_AFTER = 'stop_after'
