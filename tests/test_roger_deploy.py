#!/usr/bin/python

from __future__ import print_function
import unittest
import argparse
import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, "cli")))
import roger_push
from roger_deploy import RogerDeploy
from cli.roger_build import RogerBuild
from cli.roger_gitpull import RogerGitPull
from cli.roger_push import RogerPush
import roger_gitpull
from marathon import Marathon
from frameworkUtils import FrameworkUtils
from appconfig import AppConfig
from settings import Settings
from hooks import Hooks
from mockito import mock, when, verify
from mockito.matchers import any
from mock import MagicMock
from settings import Settings
from gitutils import GitUtils
from cli.dockerutils import DockerUtils
from cli.docker_build import Docker
from statsd import StatsClient
from cli.utils import Utils

# Test basic functionalities of roger-deploy script


class TestDeploy(unittest.TestCase):

    def setUp(self):
        parser = argparse.ArgumentParser(description='Args for test')
        parser.add_argument('-e', '--environment', metavar='env',
                            help="Environment to deploy to. example: 'dev' or 'stage'")
        parser.add_argument('-s', '--skip-build', action="store_true",
                            help="Flag that skips roger-build when set to true. Defaults to false.'")
        parser.add_argument('-M', '--incr-major', action="store_true",
                            help="Increment major in version. Defaults to false.'")
        parser.add_argument('-p', '--incr-patch', action="store_true",
                            help="Increment patch in version. Defaults to false.'")
        parser.add_argument('-sp', '--skip-push', action="store_true",
                            help="Flag that skips roger push when set to true. Defaults to false.'")
        parser.add_argument(
            '-S', '--secrets-file', help="Specify an optional secrets file for deployment runtime variables.")
        parser.add_argument(
            '-d', '--directory', help="Specify an optional directory to pull out the repo. This is the working directory.")
        self.parser = parser
        self.args = parser

        self.settingObj = Settings()
        self.base_dir = self.settingObj.getCliDir()
        self.configs_dir = self.base_dir + "/tests/configs"

        config = {u'repo': u'roger', u'notifications': {u'username': u'Roger Deploy', u'method': u'chat.postMessage', u'channel': u'Channel ID', u'emoji': u':rocket:'},
                  u'apps': {u'test_app': {u'imageBase': u'test_app_base', u'name': u'test_app', u'containers': [u'container_name1', u'container_name2']},
                            u'test_app1': {u'framework': u'chronos', u'name': u'test_app1', u'containers': [u'container_name1', u'container_name2'], u'imageBase': u'test_app_base'},
                            u'grafana_test_app': {u'imageBase': u'test_app_base', u'name': u'test_app_grafana', u'containers': [u'grafana', {u'grafana1': {u'vars': {u'environment': {u'prod': {u'mem': u'2048', u'cpus': u'2'}, u'dev': {u'mem': u'512', u'cpus': u'0.5'}},
                                                                                                                                                                     u'global': {u'mem': u'128', u'cpus': u'0.1'}}}}, {u'grafana2': {u'vars': {u'environment': {u'prod': {u'mem': u'2048', u'cpus': u'2'}, u'dev': {u'mem': u'1024', u'cpus': u'1'}},
                                                                                                                                                                                                                                               u'global': {u'mem': u'128', u'cpus': u'0.1'}}}}]}}, u'name': u'test-app', u'vars': {u'environment': {u'prod': {u'mem': u'2048', u'cpus': u'2'}, u'dev': {u'mem': u'512', u'cpus': u'1'},
                                                                                                                                                                                                                                                                                                                                                    u'stage': {u'mem': u'1024', u'cpus': u'1'}}, u'global': {u'instances': u'1', u'network': u'BRIDGE'}}}

        roger_env = {u'default_environment': u'dev', u'registry': u'example.com:5000', u'environments': {u'prod': {u'chronos_endpoint': u'http://prod.example.com:4400',
                                                                                                         u'marathon_endpoint': u'http://prod.example.com:8080'}, u'dev': {u'chronos_endpoint': u'http://dev.example.com:4400', u'marathon_endpoint': u'http://dev.example.com:8080'},
                                                                                                         u'stage': {u'chronos_endpoint': u'http://stage.example.com:4400', u'marathon_endpoint': u'http://stage.example.com:8080'}}}

        data = config['apps']['grafana_test_app']
        self.config = config
        self.roger_env = roger_env
        self.data = data

    def test_splitVersion(self):
        roger_deploy = RogerDeploy()
        assert roger_deploy.splitVersion("0.1.0") == (0, 1, 0)
        assert roger_deploy.splitVersion("2.0013") == (2, 13, 0)

    def test_incrementVersion(self):
        git_sha = "dwqjdqgwd7y12edq21"
        image_version_list = ['0.001', '0.2.034', '1.1.2', '1.002.1']
        roger_deploy = RogerDeploy()
        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.incr_patch = True
        args.incr_major = True

        assert roger_deploy.incrementVersion(
            git_sha, image_version_list, args) == 'dwqjdqgwd7y12edq21/v2.0.0'
        assert roger_deploy.incrementVersion(
            git_sha, image_version_list, args) == 'dwqjdqgwd7y12edq21/v2.0.0'
        assert roger_deploy.incrementVersion(
            git_sha, image_version_list, args) == 'dwqjdqgwd7y12edq21/v2.0.0'

    def test_tempDirCheck(self):
        work_dir = "./test_dir"
        roger_deploy = RogerDeploy()
        args = self.args
        args.directory = ""
        args.skip_push = False
        args.secrets_file = ""
        temp_dir_created = True
        roger_deploy.removeDirTree(work_dir, args, temp_dir_created)
        exists = os.path.exists(os.path.abspath(work_dir))
        assert exists is False
        os.makedirs(work_dir)
        exists = os.path.exists(os.path.abspath(work_dir))
        assert exists is True
        roger_deploy.removeDirTree(work_dir, args, temp_dir_created)
        exists = os.path.exists(os.path.abspath(work_dir))
        assert exists is False

    def test_roger_deploy_with_no_app(self):
        try:
            raised_exception = False
            settings = mock(Settings)
            appConfig = mock(AppConfig)
            roger_deploy = RogerDeploy()
            marathon = mock(Marathon)
            gitObj = mock(GitUtils)
            mockedHooks = mock(Hooks)
            roger_deploy.rogerGitPullObject = mock(RogerGitPull)
            roger_deploy.rogerPushObject = mock(RogerPush)
            roger_deploy.rogerBuildObject = mock(RogerBuild)
            roger_deploy.dockerUtilsObject = mock(DockerUtils)
            roger_deploy.dockerObject = mock(Docker)
            roger_deploy.utils = mock(Utils)
            roger_env = self.roger_env
            config = self.config
            data = self.data

            sc = mock(StatsClient)
            when(sc).timing(any(), any()).thenReturn(any())
            when(roger_deploy.utils).getStatsClient().thenReturn(sc)
            when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
            when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

            when(marathon).getCurrentImageVersion(
                any(), any(), any()).thenReturn("testversion/v0.1.0")
            frameworkUtils = mock(FrameworkUtils)
            when(frameworkUtils).getFramework(data).thenReturn(marathon)
            when(settings).getConfigDir().thenReturn(any())
            when(settings).getCliDir().thenReturn(any())
            when(settings).getUser().thenReturn('test_user')
            when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
            when(appConfig).getConfig(any(), any()).thenReturn(config)
            when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

            args = self.args
            args.directory = ""
            args.secrets_file = ""
            args.environment = "dev"
            args.skip_push = False
            args.application = ''
            args.config_file = 'test.json'
            args.skip_build = True
            args.branch = None
            os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        except:
            raised_exception = True
        self.assertFalse(raised_exception)

    def test_roger_deploy_with_no_registry_fails(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        gitObj = mock(GitUtils)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)
        mockedHooks = mock(Hooks)
        roger_env = self.roger_env
        config = self.config
        data = self.data
        sc = mock(StatsClient)

        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")
        when(marathon).getCurrentImageVersion(
            any(), any(), any(), any()).thenReturn("testversion/v0.1.0")
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn(any())
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = "dev"
        args.skip_push = False
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir

        roger_env = appConfig.getRogerEnv(self.configs_dir)
        del roger_env['registry']
        with self.assertRaises(ValueError):
            roger_deploy.main(settings, appConfig,
                              frameworkUtils, gitObj, mockedHooks, args)

    def test_roger_deploy_with_no_environment_fails(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        mockedHooks = mock(Hooks)
        gitObj = mock(GitUtils)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)
        roger_env = self.roger_env
        config = self.config
        data = self.data

        sc = mock(StatsClient)
        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

        when(marathon).getCurrentImageVersion(
            any(), any(), any()).thenReturn("testversion/v0.1.0")
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = ""
        args.skip_push = False
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        with self.assertRaises(ValueError):
            roger_deploy.main(settings, appConfig,
                              frameworkUtils, gitObj, mockedHooks, args)

    def test_rogerDeploy(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        gitObj = mock(GitUtils)
        mockedHooks = mock(Hooks)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)
        roger_env = self.roger_env
        config = self.config
        data = self.data

        repo_name = 'roger'
        repo_url = 'test_url'
        random = 'test'

        when(marathon).getCurrentImageVersion(
            any(), any(), any()).thenReturn("testversion/v0.1.0")
        when(marathon).getName().thenReturn('Marathon')
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)

        sc = mock(StatsClient)
        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)
        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(gitObj).gitClone(any(), any()).thenReturn(0)
        when(gitObj).getGitSha(any(), any(), any()).thenReturn(random)

        when(roger_deploy.rogerGitPullObject).main(any(), any(), any(), any(), any()).thenReturn(0)
        when(roger_deploy.rogerPushObject).main(any(), any(), any(), any(), any()).thenReturn(0)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = "dev"
        args.skip_push = False
        args.skip_gitpull = False
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        roger_deploy.main(settings, appConfig, frameworkUtils, gitObj, mockedHooks, args)
        verify(settings, times=1).getConfigDir()
        verify(settings).getCliDir()
        verify(appConfig).getRogerEnv(any())
        verify(appConfig, times=1).getConfig(any(), any())
        verify(frameworkUtils).getFramework(data)
        verify(marathon).getCurrentImageVersion(any(), any(), any())

    def test_rogerDeploy_with_skip_push(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        gitObj = mock(GitUtils)
        mockedHooks = mock(Hooks)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)

        roger_env = self.roger_env

        repo_name = 'roger'
        repo_url = 'test_url'
        random = 'test'

        config = self.config
        data = self.data
        when(marathon).getCurrentImageVersion(
            any(), any(), any()).thenReturn("testversion/v0.1.0")
        when(marathon).getName().thenReturn('Marathon')
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)

        sc = mock(StatsClient)
        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)

        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(gitObj).gitClone(any(), any()).thenReturn(0)
        when(gitObj).getGitSha(any(), any(), any()).thenReturn(random)

        when(roger_deploy.rogerGitPullObject).main(any(), any(), any(), any(), any()).thenReturn(0)
        when(roger_deploy.rogerPushObject).main(any(), any(), any(), any(), any()).thenReturn(0)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = "dev"
        args.skip_push = True
        args.skip_gitpull = False
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        roger_deploy.main(settings, appConfig, frameworkUtils, gitObj, mockedHooks, args)
        verify(settings, times=1).getConfigDir()
        verify(settings).getCliDir()
        verify(appConfig).getRogerEnv(any())
        verify(appConfig, times=1).getConfig(any(), any())
        verify(frameworkUtils).getFramework(data)
        verify(marathon).getCurrentImageVersion(any(), any(), any())

    def test_rogerDeploy_with_skip_gitpull_false(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        gitObj = mock(GitUtils)
        mockedHooks = mock(Hooks)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)

        roger_env = self.roger_env

        repo_name = 'roger'
        repo_url = 'test_url'
        random = 'test'

        config = self.config
        data = self.data

        sc = mock(StatsClient)
        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

        when(marathon).getCurrentImageVersion(
            any(), any(), any()).thenReturn("testversion/v0.1.0")
        when(marathon).getName().thenReturn('Marathon')
        frameworkUtils = mock(FrameworkUtils)
        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)

        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)

        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(gitObj).gitClone(any(), any()).thenReturn(0)
        when(gitObj).getGitSha(any(), any(), any()).thenReturn(random)

        when(roger_deploy.rogerGitPullObject).main(any(), any(), any(), any(), any()).thenReturn(0)
        when(roger_deploy.rogerPushObject).main(any(), any(), any(), any(), any()).thenReturn(0)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = "dev"
        args.skip_push = True
        args.skip_gitpull = False
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        roger_deploy.main(settings, appConfig, frameworkUtils, gitObj, mockedHooks, args)
        verify(roger_deploy.rogerGitPullObject, times=1).main(any(), any(), any(), any(), any())

    def test_rogerDeploy_with_skip_gitpull_true(self):
        settings = mock(Settings)
        appConfig = mock(AppConfig)
        roger_deploy = RogerDeploy()
        marathon = mock(Marathon)
        gitObj = mock(GitUtils)
        mockedHooks = mock(Hooks)
        roger_deploy.rogerGitPullObject = mock(RogerGitPull)
        roger_deploy.rogerPushObject = mock(RogerPush)
        roger_deploy.rogerBuildObject = mock(RogerBuild)
        roger_deploy.dockerUtilsObject = mock(DockerUtils)
        roger_deploy.dockerObject = mock(Docker)
        roger_deploy.utils = mock(Utils)

        roger_env = self.roger_env

        repo_name = 'roger'
        repo_url = 'test_url'
        random = 'test'

        config = self.config
        data = self.data
        when(marathon).getCurrentImageVersion(
            any(), any(), any()).thenReturn("testversion/v0.1.0")
        when(marathon).getName().thenReturn('Marathon')
        frameworkUtils = mock(FrameworkUtils)

        sc = mock(StatsClient)
        when(sc).timing(any(), any()).thenReturn(any())
        when(roger_deploy.utils).getStatsClient().thenReturn(sc)
        when(roger_deploy.utils).get_identifier(any(), any(), any()).thenReturn(any())
        when(roger_deploy.utils).extract_app_name(any()).thenReturn("test")

        when(frameworkUtils).getFramework(data).thenReturn(marathon)
        when(settings).getConfigDir().thenReturn(any())
        when(settings).getCliDir().thenReturn(any())
        when(settings).getUser().thenReturn('test_user')
        when(appConfig).getRogerEnv(any()).thenReturn(roger_env)
        when(appConfig).getConfig(any(), any()).thenReturn(config)
        when(appConfig).getAppData(any(), any(), any()).thenReturn(data)

        when(appConfig).getRepoUrl(any()).thenReturn(repo_name)
        when(appConfig).getRepoName(any()).thenReturn(repo_name)

        when(mockedHooks).run_hook(any(), any(), any(), any()).thenReturn(0)

        when(gitObj).gitPull(any()).thenReturn(0)
        when(gitObj).gitShallowClone(any(), any()).thenReturn(0)
        when(gitObj).gitClone(any(), any()).thenReturn(0)
        when(gitObj).getGitSha(any(), any(), any()).thenReturn(random)

        when(roger_deploy.rogerGitPullObject).main(any(), any(), any(), any(), any()).thenReturn(0)
        when(roger_deploy.rogerPushObject).main(any(), any(), any(), any(), any()).thenReturn(0)

        args = self.args
        args.directory = ""
        args.secrets_file = ""
        args.environment = "dev"
        args.skip_push = True
        args.skip_gitpull = True
        args.application = 'grafana_test_app'
        args.config_file = 'test.json'
        args.skip_build = True
        args.branch = None
        os.environ["ROGER_CONFIG_DIR"] = self.configs_dir
        roger_deploy.main(settings, appConfig, frameworkUtils, gitObj, mockedHooks, args)
        verify(roger_deploy.rogerGitPullObject, times=0).main(any(), any(), any(), any(), any())

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
