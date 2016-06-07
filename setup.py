"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from codecs import open
from os import path
import sys
from setuptools.command.test import test as TestCommand

here = path.abspath(path.dirname(__file__))


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, "VERSION")) as f:
    version = f.read().strip()

setup(
    name='roger-mesos-tools',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version,
    description='A set of tools/scripts to interact with RogerOS via the command line',
    long_description=long_description,
    url='https://github.com/seomoz/roger-mesos-tools',
    author='RogerOS Team',
    author_email='rogeros-dev@moz.com',
    license='Apache 2.0',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: Apache 2.0 License',
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='sample setuptools development',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(),
    tests_require=['pytest'],
    cmdclass={'test': PyTest},
    # Including test_suite to executable
    test_suite="tests",

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['argparse', 'setuptools', 'requests', 'pyyaml',
        'mock', 'mockito', 'tabulate', 'slackclient', 'Jinja2', 'statsd'],

    # Include the folders listed in the MANIFEST.in file as a part of the
    # package
    include_package_data=True,

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'roger=bin.roger:main', 'j2y=bin.j2y:main'
        ]
    },
    scripts={ 'cli/roger_build.py', 'cli/roger_deploy.py', 'cli/roger_gitpull.py', 'cli/roger_init.py', 'cli/roger_logs.py', 'cli/roger_ps.py', 'cli/roger_push.py', 'cli/roger_shell.py' }
)
