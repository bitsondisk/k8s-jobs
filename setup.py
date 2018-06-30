#!/usr/bin/env python3

from setuptools import setup, find_packages
import re


with open('k8s_jobs/__init__.py', 'r') as fp:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fp.read(), re.MULTILINE).group(1)


if not version:
    raise RuntimeError('Cannot find version information')


setup(name='k8s-jobs',
      version=version,
      author='David Tulga',
      author_email='david.tulga@freenome.com',
      description='Kubernetes job management scripts',
      py_modules=['k8s_jobs'],
      install_requires=['pyyaml'],
      scripts=['bin/kbatch',
               'bin/kcancel',
               'bin/klist',
               'bin/krun',
               'bin/kstatus',
               'bin/klogs',
               'bin/kpods',
               'bin/kexec'],
      package_data={'k8s_jobs': ['*.yaml']},
      packages=find_packages())
