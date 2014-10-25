

class Options:
  '''
  Available options
  '''

  def __init__(self, options=None):
      self.options = options

  def get_option(self, option):
    '''
    Gets an option if present, else return None
    '''
    if self.options is None:
      return None

    #if option in self.options:
    if hasattr(self.options, option):
      return self.options[option]

    return None

  NO_PUBLISH = 'no_publish'
  STOP_BEFORE = 'stop_before'
  STOP_AFTER = 'stop_after'
  FROMSCRATCH = 'fromscratch'
