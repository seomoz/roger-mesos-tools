#!/usr/bin/python

from __future__ import print_function
import unittest
import os
import sys
sys.path.append('/vagrant/cli')
import imp
roger_push = imp.load_source('roger_push', '/vagrant/cli/roger-push')

#Test basic functionalities of roger-push script
class TestPush(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

if __name__ == '__main__':
  unittest.main()
