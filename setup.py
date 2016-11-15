try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

from distutils.command.install import install
import os


class post_install(install):
    def run(self):
        install.run(self)
        from biomaj.schema_version import SchemaVersion
        SchemaVersion.migrate_pendings()

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()


config = {
    'description': 'BioMAJ',
    'long_description': README + '\n\n' + CHANGES,
    'author': 'Olivier Sallou',
    'url': 'http://biomaj.genouest.org',
    'download_url': 'http://biomaj.genouest.org',
    'author_email': 'olivier.sallou@irisa.fr',
    'version': '3.0.20',
     'classifiers': [
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4'
    ],
    'install_requires': ['nose',
                         'pymongo==3.2',
                         'pycurl',
                         'ldap3==1.4.0',
                         'mock',
                         'py-bcrypt',
                         'drmaa',
                         'future',
                         'tabulate',
                         'elasticsearch'],
    'packages': find_packages(),
    'include_package_data': True,
    'scripts': ['bin/biomaj-cli.py'],
    'name': 'biomaj',
    'cmdclass': {'install': post_install},
}

setup(**config)
