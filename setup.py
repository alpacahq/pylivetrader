#!/usr/bin/env python
# coding: utf-8
from setuptools import setup, find_packages

from pylivetrader._version import VERSION

setup(
    name='pylivetrader',
    version=VERSION,
    description='simple live trading framework',
    license='Apache 2.0',
    author='Sho Yoshida',
    author_email='nya060@gmail.com',
    url='https://github.com/alpacahq/pylivetrader.git',
    keywords='',
    packages=find_packages(),
    include_package_data=True,
    entry_points='''
    [console_scripts]
    pylivetrader=pylivetrader.__main__:main
    ''',
    install_requires=[
        'pandas',
        'numpy<1.15.0',
        'pytz',
        'logbook',
        'astor',
        'trading_calendars',
        'click',
        # supoort alpaca backend by default
        'alpaca-trade-api',
    ],
    tests_require=[
        'pytest',
    ],
    setup_requires=["flake8", "pytest-runner"],
    extras_require={}
)
