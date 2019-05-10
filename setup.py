#!/usr/bin/env python
# coding: utf-8
from setuptools import setup, find_packages

from runpy import run_path
from pathlib import Path


VERSION = run_path(
    str(Path(__file__).parent) + '/pylivetrader/_version.py')['VERSION']


with open(str(Path(__file__).parent) + '/README.md') as readme_file:
    README = readme_file.read()


setup(
    name='pylivetrader',
    version=VERSION,
    description='simple live trading framework',
    long_description=README,
    long_description_content_type='text/markdown',
    license='Apache 2.0',
    author='Alpaca',
    author_email='oss@alpaca.markets',
    url='https://github.com/alpacahq/pylivetrader.git',
    keywords='financial,zipline,pipeline,stock,screening,api,trade',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial',
    ],
    packages=find_packages(),
    include_package_data=True,
    entry_points='''
    [console_scripts]
    pylivetrader=pylivetrader.__main__:main
    ''',
    install_requires=[
        'pandas<0.24.0',
        'numpy',
        'pytz',
        'logbook',
        'astor',
        'trading_calendars',
        'click',
        'PyYAML',
        'ipython',
        # support alpaca backend by default
        'alpaca-trade-api>=0.27',
    ],
    tests_require=[
        'pytest',
        'pytest-cov',
    ],
    setup_requires=["flake8", "pytest-runner"],
    extras_require={
        "redis": ["redis"]
    }
)
