#!/usr/bin/env python
# coding: utf-8
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from pylivetrader import __author__, __version__, __license__


setup(
    name='pylivetrader',
    version=__version__,
    description='simple live trading framework',
    license=__license__,
    author=__author__,
    author_email='nya060@gmail.com',
    url='https://github.com/alpacahq/pylivetrader.git',
    keywords='',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'numpy',
    ],
    tests_require=[
        'nose',
    ],
    setup_requires=["flake8"]
)
