from builtins import object


class Options(object):
    """
    Available options
    """

    def __init__(self, options=None):
        self.options = options

    def get_option(self, option):
        """
        Gets an option if present, else return None
        """
        if hasattr(self, option):
            return getattr(self, option)
        return None

    UPDATE = 'update'
    REMOVE = 'remove'
    PUBLISH = 'publish'
    FROM_TASK = 'from_task'
    PROCESS = 'process'
    STOP_BEFORE = 'stop_before'
    STOP_AFTER = 'stop_after'
    FROMSCRATCH = 'fromscratch'
