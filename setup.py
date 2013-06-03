#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

args = {
    'name': 'streaming_multipart',
    'version': __import__("streaming_multipart").__version__,
    'url' : "http://github.com/rckclmbr/streaming_multipart",
    'description': "A streaming multipart/form-data parser for python",
    'long_description': """A streaming multipart/form-data parser, based off go's mime/multipart parser.  Written for Space Monkey""",
    'author': 'Josh Braegger',
    'author_email': 'rckclmbr@gmail.com',
    'maintainer': 'Josh Braegger',
    'maintainer_email': 'rckclmbr@gmail.com',
    'license': 'BSD',
    'packages': ["streaming_multipart"],
    'package_dir': {'': 'src'},
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
}

setup(**args)

