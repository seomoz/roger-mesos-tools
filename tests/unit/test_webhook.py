#!/usr/bin/python

from __future__ import print_function
import unittest
import os
import sys
import yaml
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from mockito import mock, when, verify, verifyZeroInteractions
from mock import MagicMock
from slackclient import SlackClient
from mockito.matchers import any
from cli.utils import Utils
from cli.appconfig import AppConfig
from cli.settings import Settings
from cli.webhook import WebHook

import pytest
# Test basic functionalities of Webhook class


class TestWebhook(unittest.TestCase):

    def setUp(self):
        self.webhook = WebHook()
        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"
        self.components_dir = self.base_dir + '/tests/components/dev'
        with open(self.configs_dir + '/roger-mesos-tools.config') as roger:
            roger_env = yaml.load(roger)
        self.roger_env = roger_env

# check for value error / exception assert
# check for one positive case - May be introduce exit code or something

    @pytest.mark.skip
    def test_invoke_webhook_when_hook_input_metrics_is_invalid(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        appdata = 'valid-app-data'
        conf_file = 'roger-mesos-tools.config'
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(appConfig).getRogerEnv(any()).thenReturn(self.roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(conf_file)
        with self.assertRaises(ValueError):
            self.webhook.invoke_webhook(appdata, conf_file, any(), any(), any())

    @pytest.mark.skip
    def test_invoke_webhook_when_appdata_is_invalid(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        appdata = 'invalid-app-data'
        conf_file = 'roger-mesos-tools.config'
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(appConfig).getRogerEnv(any()).thenReturn(self.roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(conf_file)
        with self.assertRaises(ValueError):
            self.webhook.invoke_webhook(appdata, conf_file, any(), any(), any())

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
