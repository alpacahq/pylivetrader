#!/usr/bin/env python
# coding: utf-8
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


setup(
    name='pylivetrader',
    version='0.0.1',
    description='simple live trading framework',
    license='MIT',
    author='Sho Yoshida',
    author_email='nya060@gmail.com',
    url='https://github.com/alpacahq/pylivetrader.git',
    keywords='',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'numpy<1.15.0',
        'pytz',
        'logbook',
        'astor',
        # supoort alpaca backend by default
        'alpaca-trade-api',
    ],
    tests_require=[
        'pytest',
    ],
    setup_requires=["flake8", "pytest-runner"],
    extras_require={
        'alpaca': ['alpaca-trade-api'],
    }
)
