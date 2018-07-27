#!/usr/bin/python

import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from cli.hooks import Hooks
from mockito import mock, when, verify
from mockito.matchers import any
from cli.utils import Utils
from cli.webhook import WebHook

import pytest

class TestHooks(unittest.TestCase):

    def setUp(self):
        self.hooks = Hooks()
        self.hooks.utils = mock(Utils)
        self.appdata = {}
        self.appdata["hooks"] = dict(
            [("pre-build", "pwd && echo 'In pre build!'")])
        self.appdata["hooks"]["bad-hook-cmd"] = "garbage command"
        pass

    @pytest.mark.skip
    def test_run_hook_returns_zero_when_hook_succeeds(self):

        when(self.hooks.whobj).invoke_webhook(any(), any(), any(), any(), any(), any()).thenReturn()
        when(self.hooks.utils).get_identifier(any(), any(), any()).thenReturn(any())
        assert self.hooks.run_hook("pre-build", self.appdata, os.getcwd(), any(), any()) == 0

    @pytest.mark.skip
    def test_run_hook_returns_non_zero_when_hook_fails(self):

        when(self.hooks.whobj).invoke_webhook(any(), any(), any(), any(), any(), any()).thenReturn()
        when(self.hooks.utils).get_identifier(any(), any(), any()).thenReturn(any())
        assert self.hooks.run_hook("bad-hook-cmd", self.appdata, os.getcwd(), any(), any(), any()) != 0

    @pytest.mark.skip
    def test_run_hook_returns_zero_when_hook_is_absent(self):

        when(self.hooks.whobj).invoke_webhook(any(), any(), any(), any(), any(), any()).thenReturn()
        when(self.hooks.utils).get_identifier(any(), any(), any()).thenReturn(any())
        assert self.hooks.run_hook("absent-hook", self.appdata, os.getcwd(), any(), any()) == 0

    @pytest.mark.skip
    def test_run_hook_preserves_current_directory(self):

        when(self.hooks.whobj).invoke_webhook(any(), any(), any(), any(), any(), any()).thenReturn()
        when(self.hooks.utils).get_identifier(any(), any(), any()).thenReturn(any())
        cwd = os.getcwd()
        self.hooks.run_hook("pre-build", self.appdata, "/tmp", any(), any())
        assert cwd == os.getcwd()

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
