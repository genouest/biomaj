try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

config = {
    'description': 'BioMAJ',
    'author': 'Olivier Sallou',
    'url': 'http://biomaj.genouest.org',
    'download_url': 'http://biomaj.genouest.org',
    'author_email': 'olivier.sallou@irisa.fr',
    'version': '3.0.0',
    'install_requires': ['nose', 'pymongo', 'pycurl'],
    'packages': find_packages(),
    'scripts': ['bin/biomaj-cli.py'],
    'name': 'biomaj'
}

setup(**config)
