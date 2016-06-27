#!/usr/bin/python

from __future__ import print_function
import unittest
import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from appconfig import AppConfig
from settings import Settings

# Test basic functionalities of Settings class


class TestAppConfig(unittest.TestCase):

    def setUp(self):
        self.appObj = AppConfig()
        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"

    def test_getRogerEnv(self):
        roger_env = self.appObj.getRogerEnv(self.configs_dir)
        assert roger_env['registry'] == "example.com:5000"
        assert roger_env['default_environment'] == "dev"
        assert roger_env['environments']['dev'][
            'marathon_endpoint'] == "http://dev.example.com:8080"
        assert roger_env['environments']['prod'][
            'chronos_endpoint'] == "http://prod.example.com:4400"

    def test_getConfig(self):
        config = self.appObj.getConfig(self.configs_dir, "app.json")
        assert config['name'] == "test-app"
        assert config['repo'] == "roger"
        assert config['vars']['environment']['prod']['mem'] == "2048"
        assert len(config['apps'].keys()) == 3
        for app in config['apps']:
            assert "test_app" in app
            assert config['apps'][app]['imageBase'] == "test_app_base"

    def test_getAppData(self):
        app_data = self.appObj.getAppData(
            self.configs_dir, "app.json", "app_name")
        assert app_data == ''
        app_data = self.appObj.getAppData(
            self.configs_dir, "app.json", "test_app")
        assert app_data['imageBase'] == "test_app_base"
        assert len(app_data['containers']) == 2

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
