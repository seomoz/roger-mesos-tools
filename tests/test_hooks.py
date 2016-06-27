#!/usr/bin/python

import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from hooks import Hooks
from mockito import mock, when, verify
from cli.utils import Utils


class TestHooks(unittest.TestCase):

    def setUp(self):
        self.hooks = Hooks()
        self.appdata = {}
        self.appdata["hooks"] = dict(
            [("pre-build", "pwd && echo 'In pre build!'")])
        self.appdata["hooks"]["bad-hook-cmd"] = "garbage command"
        pass

    def test_run_hook_returns_zero_when_hook_succeeds(self):
        self.utils = mock(Utils)
        assert self.hooks.run_hook("pre-build", self.appdata, os.getcwd(), "roger-tools.pre-build-test") == 0

    def test_run_hook_returns_non_zero_when_hook_fails(self):
        self.utils = mock(Utils)
        assert self.hooks.run_hook(
            "bad-hook-cmd", self.appdata, os.getcwd(), "roger-tools.bad-hook-cmd-test") != 0

    def test_run_hook_returns_zero_when_hook_is_absent(self):
        self.utils = mock(Utils)
        assert self.hooks.run_hook(
            "absent-hook", self.appdata, os.getcwd(), "roger-tools.absent-hook-test") == 0

    def test_run_hook_preserves_current_directory(self):
        self.utils = mock(Utils)
        cwd = os.getcwd()
        self.hooks.run_hook("pre-build", self.appdata, "/tmp", "roger-tools.pre-build-tmp-test")
        assert cwd == os.getcwd()

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
