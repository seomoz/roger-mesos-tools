#!/usr/bin/python

from __future__ import print_function
import unittest
import os
import json
import yaml
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
from roger_gitpull import RogerGitPull
import argparse
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.hooks import Hooks
from mockito import mock, when, verify
from mockito.matchers import any
from cli.marathon import Marathon
from cli.gitutils import GitUtils
from cli.frameworkUtils import FrameworkUtils
from cli.utils import Utils


# Test basic functionalities of roger-git-pull script


class TestGitPull(unittest.TestCase):

    def setUp(self):
        parser = argparse.ArgumentParser(description='Args for test')
        parser.add_argument('app_name', metavar='app_name',
                            help="application for which code is to be pulled. Example: 'agora' or 'grafana'")
        parser.add_argument('directory', metavar='directory',
                            help="working directory. The repo has its own directory it this. Example: '/home/vagrant/work_dir'")
        parser.add_argument('-b', '--branch', metavar='branch',
                            help="git branch to pull code from. Example: 'production' or 'master'. Defaults to master.")
        parser.add_argument('config_file', metavar='config_file',
                            help="configuration file to use. Example: 'content.json' or 'kwe.json'")

        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"
        self.work_dir = self.base_dir + "/tests/work_dir"
        self.components_dir = self.base_dir + '/tests/components/dev'
        self.args = parser

        with open(self.configs_dir + '/app.json') as config:
            config = json.load(config)
        with open(self.configs_dir + '/roger-mesos-tools.config') as roger:
            roger_env = yaml.load(roger)

        data = config['apps']['grafana_test_app']
        self.roger_env = roger_env
        self.data = data
        self.config = config

        pass

    def test_rogerGitPull(self):
        set_config_dir = ''
        if "ROGER_CONFIG_DIR" in os.environ:
            set_config_dir = os.environ.get('ROGER_CONFIG_DIR')
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        config_file = "app.json"
        work_dir = self.work_dir
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_gitpull = RogerGitPull()
        roger_gitpull.utils = mock(Utils)
        marathon = mock(Marathon)
        mockedHooks = mock(Hooks)
        gitObj = mock(GitUtils)
        data = self.data
        config = self.config
        roger_env = self.roger_env
        repo_name = 'roger'

        when(roger_gitpull.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_gitpull.utils).extract_app_name(any()).thenReturn("test")

        when(marathon).put(self.components_dir + '/test-roger-grafana.json',
                           roger_env['environments']['dev'], 'grafana_test_app').thenReturn("Response [200]")
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getComponentsDir().thenReturn(
            self.base_dir + "/tests/components")
        when(settings).getSecretsDir().thenReturn(
            self.base_dir + "/tests/secrets")
        when(settings).getTemplatesDir().thenReturn(
            self.base_dir + "/tests/templates")
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(settings).getCliDir().thenReturn(self.base_dir)
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(self.configs_dir).thenReturn(roger_env)
        when(appConfig).getConfig(
            self.configs_dir, "app.json").thenReturn(config)
        when(appConfig).getAppData(self.configs_dir,
                                   "app.json", "grafana_test_app").thenReturn(data)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)

        args = self.args
        args.app_name = "grafana_test_app"
        args.config_file = config_file
        args.branch = "master"
        args.environment = 'test'
        args.directory = self.work_dir
        args.verbose = False
        when(mockedHooks).run_hook(any(), any(), any(), any(), any(), any()).thenReturn(0)
        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        raised_exception = False
        try:
            return_code = roger_gitpull.main(settings, appConfig, gitObj, mockedHooks, args)
        except (Exception) as e:
            raised_exception = True
        self.assertTrue(raised_exception)
        with open(self.configs_dir + '/{}'.format(config_file)) as config:
            config = json.load(config)
        exists = os.path.exists(work_dir)
        assert exists is True
        shutil.rmtree(work_dir)
        if set_config_dir.strip() != '':
            os.environ["ROGER_CONFIG_DIR"] = "{}".format(set_config_dir)

    def test_roger_gitpull_calls_pregitpull_hook_when_present(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_gitpull = RogerGitPull()
        mockedHooks = mock(Hooks)
        gitObj = mock(GitUtils)
        roger_env = {}
        roger_env["registry"] = "any registry"
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        appdata = {}
        appdata["hooks"] = dict([("pre_gitpull", "some command")])
        repo_name = 'roger'
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(appdata)
        config = self.config

        when(roger_gitpull.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_gitpull.utils).extract_app_name(any()).thenReturn("test")
        when(settings).getUser().thenReturn('test_user')

        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)
        args = self.args
        args.config_file = 'any.json'
        args.app_name = 'any app'
        args.environment = 'test'
        args.branch = "some_branch"
        args.directory = '/tmp'
        args.verbose = False
        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(mockedHooks).run_hook(any(), any(), any(), any(), any(), any()).thenReturn(0)
        raised_exception = False
        try:
            return_code = roger_gitpull.main(settings, appConfig, gitObj, mockedHooks, args)
        except (Exception) as e:
            raised_exception = True
        self.assertTrue(raised_exception)
        verify(mockedHooks).run_hook("pre_gitpull", any(), any(), any())

    def test_roger_gitpull_calls_postgitpull_hook_when_present(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_gitpull = RogerGitPull()
        roger_gitpull.utils = mock(Utils)
        mockedHooks = mock(Hooks)
        gitObj = mock(GitUtils)
        roger_env = {}
        repo_name = 'roger'
        repo_url = 'test_url'
        roger_env["registry"] = "any registry"
        when(settings).getConfigDir().thenReturn(self.configs_dir)
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        appdata = {}
        appdata["hooks"] = dict([("post_gitpull", "some command")])
        when(appConfig).getAppData(any(), any(), any()).thenReturn(appdata)
        config = self.config

        when(roger_gitpull.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_gitpull.utils).extract_app_name(any()).thenReturn("test")

        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)
        args = self.args
        args.config_file = 'any.json'
        args.app_name = 'any app'
        args.branch = "some_branch"
        args.directory = '/tmp'
        args.environment = 'test'
        args.verbose = False
        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(mockedHooks).run_hook(any(), any(), any(), any(), any(), any()).thenReturn(0)
        raised_exception = False
        try:
            return_code = roger_gitpull.main(settings, appConfig, gitObj, mockedHooks, args)
            verify(mockedHooks).run_hook("post_gitpull", any(), any(), any())
        except (Exception) as e:
            raised_exception = True
        self.assertTrue(raised_exception)

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
