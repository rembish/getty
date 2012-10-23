from distutils.core import setup
from setuptools import find_packages
from os.path import abspath, dirname, join

from getty import __version__

readme = join(dirname(abspath(__file__)), 'README.rst')

setup(
    name='getty',
    version=__version__,
    packages=find_packages(),
    url='https://github.com/don-ramon/getty',
    license='BSD',
    author='Aleksey Rembish',
    author_email='alex@rembish.ru',
    description='Getty Images Bank API Client',
    long_description=''.join(open(readme, 'rt').readlines()),
    install_requires=[
        "simplejson",
        "requests",
    ]
)
