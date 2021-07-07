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
        SchemaVersion.add_property(prop='desc', cfg='db.fullname')
        SchemaVersion.set_version()

here = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(here, 'README.md')) as f:
        README = f.read()
    with open(os.path.join(here, 'CHANGES.txt')) as f:
        CHANGES = f.read()
except UnicodeDecodeError:
    with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        README = f.read()
    with open(os.path.join(here, 'CHANGES.txt'), encoding='utf-8') as f:
        CHANGES = f.read()


config = {
    'description': 'BioMAJ',
    'long_description': README + '\n\n' + CHANGES,
    'long_description_content_type': 'text/markdown',
    'author': 'Olivier Sallou',
    'url': 'http://biomaj.genouest.org',
    'download_url': 'http://biomaj.genouest.org',
    'author_email': 'olivier.sallou@irisa.fr',
    'version': '3.1.20',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6'
    ],
    'install_requires': [
                         'biomaj_cli',
                         'biomaj_core',
                         'biomaj_user',
                         'biomaj_download',
                         'biomaj_process',
                         'pymongo>=3.2',
                         'pycurl',
                         'py-bcrypt',
                         'drmaa',
                         'future',
                         'tabulate',
                         'requests',
                         'redis',
                         'elasticsearch',
                         'influxdb',
                         'Yapsy==1.12.2',
                         'packaging'
                         ],
    'tests_require': ['nose', 'mock'],
    'test_suite': 'nose.collector',
    'packages': find_packages(),
    'include_package_data': True,
    'scripts': ['scripts/biomaj_migrate_database.py'],
    'name': 'biomaj',
    #'cmdclass': {'install': post_install},
}

setup(**config)
