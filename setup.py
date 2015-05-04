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
    'version': '3.0.4',
    'install_requires': ['nose',
                            'pymongo',
                            'pycurl',
                            'ldap3',
                            'mock',
                            'py-bcrypt',
                            'mock',
                            'drmaa',
                            'future',
                            'elasticsearch'],
    'packages': find_packages(),
    'include_package_data': True,
    'scripts': ['bin/biomaj-cli.py'],
    'name': 'biomaj'
}

setup(**config)
