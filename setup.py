#!/usr/bin/env python

import os
from setuptools import setup


here = os.path.abspath(os.path.dirname(__file__))


def readme():
    with open("README.rst") as f:
        return f.read()


def read_requirements():
    with open("requirements.txt") as fp:
        return [row.strip() for row in fp if row.strip()]


about: dict = {}
with open(os.path.join(here, "ptwit.py"), "r") as f:
    while True:
        line = f.readline()
        if not line:
            break
        if line.startswith("__VERSION__"):
            exec(line, about)
            break


setup(
    name="ptwit",
    version=about["__VERSION__"],
    description="A simple twitter command line client",
    long_description=readme(),
    classifiers=[
        "Development Status :: 5 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Utilities",
    ],
    url="https://github.com/ptpt/ptwit",
    author="Tao Peng",
    author_email="ptpttt+ptwit@gmail.com",
    keywords="twitter, command-line, client",
    license="MIT",
    py_modules=["ptwit"],
    install_requires=read_requirements(),
    entry_points="""
      [console_scripts]
      ptwit=ptwit:cli
      """,
    zip_safe=False,
)
