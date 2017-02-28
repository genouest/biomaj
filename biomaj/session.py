from future import standard_library
from builtins import str
from builtins import object
import os
import time
import copy
import sys

from biomaj.workflow import Workflow

standard_library.install_aliases()


class Session(object):
    """
    BioMAJ bank session
    """
    OVER = 0

    @staticmethod
    def get_ordered_dict():
        if sys.version_info < (2, 7):
            return {}
        else:
            import collections
            return collections.OrderedDict()

    def __init__(self, name, config, flow=None, action='update'):
        """
        Creates a new session

        :param name: Name of the bank
        :type name: str
        :param config: bank and global config
        :type config: BiomajConfig
        :param flow: Workflow tasks
        :param action: type of flow update|remove
        :type action: str
        :type flow: dict
        """
        if flow is None:
            flow = Workflow.FLOW
        self.name = name
        self.config = config
        self.flow = copy.deepcopy(flow)
        self._reset_done = False

        formats = {}
        if self.config.get('db.formats') is not None:
            flist = self.config.get('db.formats').split(',')
            for f_in_list in flist:
                formats[f_in_list.strip()] = []

        self._session = {
            'id': time.time(),
            'log_file': self.config.log_file,
            'status': {},
            'files': [],
            'release': None,
            'remoterelease': None,
            'formats': formats,
            'process': {
                'postprocess': {},
                'preprocess': {},
                'removeprocess': {}
            },
            'per_process_metadata': {},
            'data_dir': self.config.get('data.dir'),
            'dir_version': self.config.get('dir.version')
        }

        for flow in self.flow:
            self._session['status'][flow['name']] = False

        self.set('last_modified', self.config.last_modified)

        # Default is update
        self._session['action'] = action

    def reload_postprocess_in_order(self, postprocess):
        """
        Reloads processes in config order
        """
        if self.config.get('BLOCKS') is None:
            return postprocess
        copy_postprocess = Session.get_ordered_dict()
        blocks = self.config.get('BLOCKS').split(',')
        for block in blocks:
            copy_postprocess[block] = Session.get_ordered_dict()
            metas = self.config.get(block.strip() + '.db.post.process').split(',')
            for meta in metas:
                copy_postprocess[block][meta] = Session.get_ordered_dict()
                processes = self.config.get(meta.strip()).split(',')
                for process in processes:
                    if block not in postprocess or meta not in postprocess[block] or process not in postprocess[block][meta]:
                        copy_postprocess[block][meta][process] = False
                    else:
                        copy_postprocess[block][meta][process] = postprocess[block][meta][process]
        return copy_postprocess

    def reload_in_order(self, cfg_type, otherprocess):
        """
        Reloads processes in config order
        """
        if self.config.get(cfg_type) is None or not self.config.get(cfg_type):
            return otherprocess
        copy_postprocess = Session.get_ordered_dict()
        metas = self.config.get(cfg_type).split(',')
        for meta in metas:
            copy_postprocess[meta] = Session.get_ordered_dict()
            processes = self.config.get(meta.strip()).split(',')
            for process in processes:
                copy_postprocess[meta][process] = otherprocess[meta][process]
        return copy_postprocess

    def reset_proc(self, type_proc, proc=None):
        """
        Reset status of processes for type in session

        :param type_proc: postprocess preprocess or removeprocess
        :type type_proc: Workflow.POSTPROCESS, Workflow.PREPROCESS, Workflow.REMOVEPROCESS
        :param proc: reset from block/meta/proc, all reset all
        :type proc: str
        """
        # If --process option not given on command line, we won't find it in following loop(s)
        if proc is None:
            self._reset_done = True
        if type_proc == Workflow.FLOW_POSTPROCESS:
            if proc in self._session['process']['postprocess']:
                self._session['process']['postprocess'] = self.reload_postprocess_in_order(self._session['process']['postprocess'])
                self.reset_meta(self._session['process']['postprocess'][proc])
            else:
                for elt in list(self._session['process']['postprocess'].keys()):
                    self.reset_meta(self._session['process']['postprocess'][elt], proc)
        elif type_proc == Workflow.FLOW_PREPROCESS:
            self._session['process']['preprocess'] = self.reload_in_order('db.pre.process', self._session['process']['preprocess'])
            self.reset_meta(self._session['process']['preprocess'])
        elif type_proc == Workflow.FLOW_REMOVEPROCESS:
            self._session['process']['removeprocess'] = self.reload_in_order('db.remove.process', self._session['process']['removeprocess'])
            self.reset_meta(self._session['process']['removeprocess'], proc)
        return self._reset_done

    def reset_meta(self, metas, proc=None):
        """
        Reset status of meta processes
        """
        if proc in metas:
            for metaproc in list(metas[proc].keys()):
                self.reset_process(metas[proc], metaproc)
        else:
            for meta in list(metas.keys()):
                self.reset_process(metas[meta], proc)

    def reset_process(self, processes, proc=None):
        """
        Reset status of processes
        """
        set_to_false = False
        for process in list(processes.keys()):
            if process == proc or proc is None:
                set_to_false = True
                self._reset_done = True
            if set_to_false:
                processes[process] = False

    def load(self, session):
        """
        Load an existing session
        """
        self._session = session

    def get_release_directory(self, release=None):
        """
        Get release directroy name

        :param release: optional release, if not set, use current session release
        :type release: str

        """
        if release is not None:
            return self.name + self.config.get('release.separator', default='_') + str(release)
        else:
            return self.name + self.config.get('release.separator', default='_') + str(self._session['release'])

    def get_full_release_directory(self, release=None):
        """
        Get bank directroy for this release

        :param release: optional release, if not set, use current session release
        :type release: str
        """
        release_dir = os.path.join(
            self._session['data_dir'],
            self._session['dir_version'],
            self.get_release_directory(release)
        )
        return release_dir

    def get_offline_directory(self):
        """
        Get bank offline directory
        """
        return os.path.join(self.config.get('data.dir'), self.config.get('offline.dir.name'))

    def get(self, attr=None):
        """
        Return an attribute of session
        """
        if attr is None:
            return self._session

        if attr in self._session:
            return self._session[attr]
        else:
            return None

    def set(self, attr, value):
        """
        Sets an attribute of session
        """
        self._session[attr] = value

    def get_status(self, status):
        """
        Return status for a flow event
        """
        if status not in self._session['status']:
            return False
        return self._session['status'][status]

    def set_status(self, status, value):
        """
        Set status for a flow event
        """
        self._session['status'][status] = value
