# roger-mesos-tools ![Build Status](https://api.travis-ci.org/seomoz/roger-mesos-tools.svg?branch=master)

Tools to connect to and work with [RogerOS](https://github.com/seomoz/roger-mesos), Moz's cluster OS based on mesos.

### Build
`$ python setup.py build`

### Run tests
`$ python setup.py test`

### Generate source distribution
`$ python setup.py sdist`

### Install
`$ python setup.py install`
OR
`pip install -e .`

### Use
* `roger -h`
* `roger <command> -h`

### Uninstall
`pip uninstall roger_mesos_tools`

### With virtualenv
```
virtualenv venv
source venv/bin/activate
pip install -e .
# run roger commands
deactivate
```
