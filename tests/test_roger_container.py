#!/usr/bin/python

from __future__ import print_function
import unittest
import os
import argparse
import json
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from roger_push import RogerPush
from marathon import Marathon
from frameworkUtils import FrameworkUtils
from appconfig import AppConfig
from settings import Settings
from mockito import mock, when, verify
from mockito.matchers import any
from mock import MagicMock
from hooks import Hooks
from cli.utils import Utils
from statsd import StatsClient

# Test basic functionalities of roger-push script


class Testcontainer(unittest.TestCase):

    def setUp(self):
        parser = argparse.ArgumentParser(description='Args for test')
        parser.add_argument('-e', '--env', metavar='env',
                            help="Environment to deploy to. example: 'dev' or 'stage'")
        parser.add_argument(
            '--skip-push', '-s', help="Don't push. Only generate components. Defaults to false.", action="store_true")
        parser.add_argument('--secrets-file', '-S',
                            help="Specify an optional secrets file for deploy runtime variables.")
        self.parser = parser
        self.args = parser

        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"

        with open(self.configs_dir + '/roger_single_container_var_tests.json') as config:
            config = json.load(config)
        with open(self.configs_dir + '/roger-env.json') as roger:
            roger_env = json.load(roger)
        data = config['apps']['container-vars']
        self.config = config
        self.roger_env = roger_env
        self.data = data

    def test_vars_single_container(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        marathon = mock(Marathon)
        mockedHooks = mock(Hooks)
        roger_push = RogerPush()
        roger_push.utils = mock(Utils)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        roger_env = self.roger_env
        config = self.config
        data = self.data
        sc = mock(StatsClient)
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(marathon).getName().thenReturn('Marathon')
        when(settings).getComponentsDir().thenReturn(
            self.base_dir + "/tests/components")
        when(settings).getSecretsDir().thenReturn(
            self.base_dir + "/tests/secrets")
        when(settings).getTemplatesDir().thenReturn(
            self.base_dir + "/tests/templates")

        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_push.utils).getStatsClient().thenReturn(sc)
        when(roger_push.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(settings).getCliDir().thenReturn(self.base_dir)
        when(settings).getUser().thenReturn(any())
        when(appConfig).getRogerEnv(self.configs_dir).thenReturn(roger_env)
        when(appConfig).getConfig(self.configs_dir,
                                  "roger_single_container_var_tests.json").thenReturn(config)

        when(appConfig).getAppData(self.configs_dir,
                                   "roger_single_container_var_tests.json", "container-vars").thenReturn(data)

        args = self.args
        args.env = "dev"
        args.skip_push = True
        args.secrets_dir = ""

        args.app_name = 'container-vars'
        args.config_file = 'roger_single_container_var_tests.json'
        args.directory = self.base_dir + '/tests/testrepo'
        args.image_name = 'tests/v0.1.0'
        args.secrets_file = 'test'

        roger_push.main(settings, appConfig, frameworkUtils, mockedHooks, args)

        with open(self.base_dir + '/tests/components/dev/roger-single-container-var-tests.json') as output:
            output = json.load(output)

        var1 = output["env"]["VAR_1"]
        var3 = output["env"]["VAR_3"]
        var4 = output["env"]["VAR_4"]

        print ("Expected Value -> Var1 : environment_value_1")
        print ("Actual Value   : {}".format(var1))

        print ("Expected Value -> Var3 : value_3")
        print ("Actual Value   : {}".format(var3))

        assert var3 == "value_3"
        assert var1 == "environment_value_1"

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
