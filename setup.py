#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='ptwit',
      version='0.2',
      description='A simple twitter command line client',
      long_description=readme(),
      classifiers=[
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'Topic :: Utilities'],
      url='https://github.com/ptpt/ptwit',
      author='Tao Peng',
      author_email='ptpttt+ptwit@gmail.com',
      keywords='twitter, command-line, client',
      license='MIT',
      py_modules=['ptwit'],
      install_requires=['python-twitter', 'click-default-group', 'click'],
      entry_points='''
      [console_scripts]
      ptwit=ptwit:cli
      ''',
      zip_safe=False)
