#!/usr/bin/python

from __future__ import print_function
import unittest
import argparse
import json
import yaml
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from roger_build import RogerBuild
from appconfig import AppConfig
from settings import Settings
from mockito import mock, when, verify
from mockito.matchers import any
from hooks import Hooks
from cli.dockerutils import DockerUtils
from cli.docker_build import Docker
from cli.utils import Utils
from statsd import StatsClient

# Test basic functionalities of roger-build script


class TestBuild(unittest.TestCase):

    def setUp(self):
        parser = argparse.ArgumentParser(description='Args for test')
        parser.add_argument('app_name', metavar='app_name',
                            help="application to build. Example: 'agora'.")
        parser.add_argument('env', metavar='env',
                            help="environment. Example: 'test'.")
        parser.add_argument('directory', metavar='directory',
                            help="working directory. Example: '/home/vagrant/work_dir'.")
        parser.add_argument('tag_name', metavar='tag_name',
                            help="tag for the built image. Example: 'roger-collectd:0.20'.")
        parser.add_argument('config_file', metavar='config_file',
                            help="configuration file to use. Example: 'content.json'.")
        parser.add_argument(
            '--push', '-p', help="Also push to registry. Defaults to false.", action="store_true")

        self.parser = parser
        self.args = self.parser
        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"
        self.components_dir = self.base_dir + '/tests/components/dev'
        with open(self.configs_dir + '/app.json') as config:
            config = json.load(config)
        with open(self.configs_dir + '/roger-mesos-tools.config') as roger:
            roger_env = yaml.load(roger)
        data = config['apps']['grafana_test_app']
        self.config = config
        self.roger_env = roger_env
        self.data = data

    def test_roger_build(self):
        try:
            settings = mock(Settings)
            appConfig = mock(AppConfig)
            dockerUtilsObj = mock(DockerUtils)
            dockerObj = mock(Docker)
            roger_build = RogerBuild()
            roger_build.utils = mock(Utils)
            mockedHooks = mock(Hooks)
            roger_env = self.roger_env
            config = self.config
            data = self.data
            repo_name = 'test'
            repo_url = 'test.com'
            raised_exception = False
            sc = mock(StatsClient)

            when(sc).timing(any(), any()).thenReturn(any())
            when(roger_build.utils).getStatsClient().thenReturn(sc)
            when(roger_build.utils).get_identifier(any(), any(), any()).thenReturn(any())
            when(roger_build.utils).verify_app_name(any()).thenReturn(any())
            when(settings, strict=False).getConfigDir().thenReturn(any())
            when(settings, strict=False).getCliDir().thenReturn(any())
            when(settings).getUser().thenReturn(any())
            when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
            when(appConfig).getConfig(any(), any()).thenReturn(config)
            when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

            when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
            when(appConfig).getRepoName(any()).thenReturn(repo_name)

            when(mockedHooks, strict=False).run_hook(any(), any(), any(), any()).thenReturn(0)

            args = self.args
            # Setting app_name as empty
            args.app_name = ''
            args.env = 'test'
            args.config_file = 'app.json'
            args.directory = self.base_dir

            # with self.assertRaises(ValueError):
            roger_build.main(settings, appConfig, mockedHooks,
                             dockerUtilsObj, dockerObj, args)
        except:
            raised_exception = True
        self.assertFalse(raised_exception)

    def test_roger_build_calls_prebuild_hook_when_present(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        dockerUtilsObj = mock(DockerUtils)
        dockerObj = mock(Docker)
        roger_build = RogerBuild()
        roger_build.utils = mock(Utils)
        mockedHooks = mock(Hooks)
        roger_env = {}
        roger_env["registry"] = "any registry"
        appdata = {}
        appdata["hooks"] = dict([("pre_build", "some command")])
        config = self.config
        args = self.args
        args.config_file = 'any.json'
        args.app_name = 'any app'
        args.env = 'test'
        args.directory = '/tmp'
        data = self.data
        repo_name = 'test'
        repo_url = 'test.com'
        sc = mock(StatsClient)

        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_build.utils).getStatsClient().thenReturn(sc)
        when(roger_build.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_build.utils).verify_app_name(any()).thenReturn("any app")
        when(settings, strict=False).getConfigDir().thenReturn(any())
        when(settings, strict=False).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn(any())
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)
        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        return_code = roger_build.main(
            settings, appConfig, mockedHooks, dockerUtilsObj, dockerObj, args)
        verify(mockedHooks).run_hook("pre_build", any(), any(), any())

    def test_roger_build_calls_postbuild_hook_when_present(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        dockerUtilsObj = mock(DockerUtils)
        dockerObj = mock(Docker)
        roger_build = RogerBuild()
        roger_build.utils = mock(Utils)
        mockedHooks = mock(Hooks)
        roger_env = {}
        roger_env["registry"] = "any registry"
        appdata = {}
        appdata["hooks"] = dict([("post_build", "some command")])
        config = self.config
        args = self.args
        args.app_name = 'any app'
        args.env = 'test'
        args.directory = '/tmp'
        args.config_file = 'any.json'
        data = self.data
        repo_name = 'test'
        repo_url = 'test.com'
        sc = mock(StatsClient)

        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_build.utils).getStatsClient().thenReturn(sc)
        when(roger_build.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_build.utils).verify_app_name(any()).thenReturn("any app")
        when(settings, strict=False).getConfigDir().thenReturn(any())
        when(settings, strict=False).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn(any())
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)
        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)

        return_code = roger_build.main(
            settings, appConfig, mockedHooks, dockerUtilsObj, dockerObj, args)
        verify(mockedHooks).run_hook("post_build", any(), any(), any())

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
