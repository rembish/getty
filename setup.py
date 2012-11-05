from distutils.core import setup
from os.path import abspath, dirname, join

readme = join(dirname(abspath(__file__)), 'README.rst')

setup(
    name='getty',
    version='0.2.0',
    py_modules=["getty"],
    url='https://github.com/don-ramon/getty',
    license='BSD',
    author='Aleksey Rembish',
    author_email='alex@rembish.ru',
    description='Getty Images Bank API Client',
    long_description=''.join(open(readme, 'rt').readlines()),
    install_requires=[
        "simplejson",
        "requests",
        'pytz',
    ],
    classifiers=[
        "Programming Language :: Python :: 2.6",
        "License :: OSI Approved :: BSD License",
        "Environment :: Web Environment",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Multimedia :: Graphics"
    ]
)
