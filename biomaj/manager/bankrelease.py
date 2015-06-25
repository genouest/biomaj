"""
Base class for bank release
"""


class BankRelease:

    def __init__(self, creation=None, path=None, session=None, size=None, kind=None,
                 download=None, release=None, started=None, ended=None, status=None,
                 removed=None, name=None, online=False):
        self.creation = creation
        self.removed = removed
        self.path = path
        self.session = session
        self.size = size
        self.kind = kind
        self.online = online
        self.download = download
        self.release = release
        self.started = started
        self.ended = ended
        self.release = 'NA'
        self.status = status
        self.name = name

    def info(self):
        """
            Prints information about a bank release
        """
        print("----------------------")
        print("Bank         : %s" % self.name)
        print("Kind         : %s" % self.kind)
        print("Available    : %s" % str(self.online))
        print("Status       : %s" % self.status)
        print("Release      : %s" % self.release)
        print("Creation     : %s" % self.creation)
        print("Removed      : %s" % self.removed)
        print("Last session : %s" % self.session)
        print("Path         : %s" % self.path)
        print("Size         : %s" % str(self.size))
        print("Downloaded   : %s" % self.download)
        print("Started      : %s" % self.started)
        print("Ended        : %s" % self.ended)
        print("Last session : %s" % self.session)
        print("----------------------")
