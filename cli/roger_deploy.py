#!/usr/bin/python

from __future__ import print_function
from tempfile import mkdtemp
import argparse
from decimal import *
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from termcolor import colored
import subprocess
import json
import os
import requests
import sys
from cli.roger_build import RogerBuild
from cli.roger_gitpull import RogerGitPull
import re
import shutil
from cli.roger_push import RogerPush
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.utils import Utils
from cli.utils import printException, printErrorMsg
from cli.hooks import Hooks
from cli.marathon import Marathon
from cli.chronos import Chronos
from cli.frameworkUtils import FrameworkUtils
from cli.gitutils import GitUtils
from cli.dockerutils import DockerUtils
from cli.docker_build import Docker
requests.packages.urllib3.disable_warnings()

import contextlib
import statsd
import urllib


@contextlib.contextmanager
def chdir(dirname):
    '''Withable chdir function that restores directory'''
    curdir = os.getcwd()
    try:
        os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


def describe():
    return 'runs through all of the steps: gitpull -> build & push to registry -> push to roger mesos.'


def getGitSha(work_dir, repo, branch, gitObj):
    return gitObj.getGitSha(repo, branch, work_dir)


def verify(value):
    for item in value.split("."):
        if not item.isdigit():
            return False
    return True


class Slack:

    def __init__(self, config, token_file):
        self.disabled = True
        try:
            from slackclient import SlackClient
        except:
            return

        try:
            self.channel = config['channel']
            self.method = config['method']
            self.username = config['username']
            self.emoji = config['emoji']
        except (TypeError, KeyError) as e:
            return

        try:
            with open(token_file) as stoken:
                r = stoken.readlines()
            slack_token = ''.join(r).strip()
            self.client = SlackClient(slack_token)
        except IOError:
            return

        self.disabled = False

    def api_call(self, text):
        if not self.disabled:
            self.client.api_call(self.method, channel=self.channel,
                                 username=self.username, icon_emoji=self.emoji, text=text)
            print ("Your current configuration for slack notifications is deprecated! Please switch to latest configuration.")

class RogerDeploy(object):

    def __init__(self):
        self.rogerGitPullObject = RogerGitPull()
        self.rogerPushObject = RogerPush()
        self.rogerBuildObject = RogerBuild()
        self.dockerUtilsObject = DockerUtils()
        self.dockerObject = Docker()
        self.utils = Utils()
        self.slack = None
        self.statsd_message_list = []
        self.registry = ""
        self.image_name = ""

        # To remove a temporary directory created by roger-deploy if this
        # script exits
    def removeDirTree(self, work_dir, args, temp_dir_created):
        exists = os.path.exists(os.path.abspath(work_dir))
        if exists and (temp_dir_created is True):
            shutil.rmtree(work_dir)
            print("Deleted temporary dir:{0}".format(work_dir))

    def getNextVersion(self, config, roger_env, application, branch, work_dir, repo, args, gitObj):
        sha = getGitSha(work_dir, repo, branch, gitObj)
        docker_search = self.dockerUtilsObject.docker_search(roger_env['registry'], config['name'], application)
        image_version_list = []
        version = ''
        envs = []
        for each_key in roger_env["environments"].keys():
            envs.append(each_key)
        for line in docker_search.split('\n'):
            image = line.split(' ')[0]
            # (vmahedia) todo: This belongs in a separate DockerImage class. This class should know
            # how to generate the image name, how to search the image or return this name pattern we
            # then use to search this image on the registry.
            matchObj = re.match("^{0}-{1}-.*/v.*".format(config['name'], application), image)
            if matchObj and matchObj.group().startswith(config['name'] + '-' + application):
                skip_image = False
                for env in envs:
                    if matchObj.group().startswith("{0}-{1}-{2}".format(config['name'], application, env)):
                        skip_image = True
                        break
                if skip_image is False:
                    if verify(str(matchObj.group().split('v')[-1])):
                        image_version_list.append(matchObj.group().split('v')[-1])

        if len(image_version_list) == 0:  # Create initial version
            version = "{0}/v0.1.0".format(sha)
            print("No version currently exist in the Docker Registry. \nDeploying version:{0}".format(
                version))
        else:
            version = self.incrementVersion(sha, image_version_list, args)
        return version

    def incrementVersion(self, sha, image_version_list, args):
        latest = max(image_version_list, key=self.splitVersion)
        ver_tuple = self.splitVersion(latest)
        latest_version = ''
        if args.incr_major:
            latest_version = "{0}/v{1}.0.0".format(sha,
                                                   (int(ver_tuple[0]) + 1))
            return latest_version
        if args.incr_patch:
            latest_version = "{0}/v{1}.{2}.{3}".format(
                sha, int(ver_tuple[0]), int(ver_tuple[1]), (int(ver_tuple[2]) + 1))
            return latest_version

        latest_version = "{0}/v{1}.{2}.0".format(
            sha, int(ver_tuple[0]), (int(ver_tuple[1]) + 1))
        return latest_version

    def splitVersion(self, version):
        major, _, rest = version.partition('.')
        minor, _, rest = rest.partition('.')
        patch, _, rest = rest.partition('.')
        return int(major), int(minor) if minor else 0, int(patch) if patch else 0

    def parseArgs(self):
        self.parser = argparse.ArgumentParser(
            prog='roger deploy', description=describe())
        self.parser.add_argument('-e', '--environment', metavar='env',
                                 help="environment to deploy to. Example: 'dev' or 'stage'")
        self.parser.add_argument('-b', '--branch', metavar='branch', default='master',
                                 help="branch to pull code from. Defaults to master. Example: 'production' or 'master'")
        self.parser.add_argument('-sg', '--skip-gitpull', action="store_true",
                                 help="skip the gitpull step. Defaults to false.")
        self.parser.add_argument('-s', '--skip-build', action="store_true",
                                 help="whether to skip the build step. Defaults to false.")
        self.parser.add_argument('-M', '--incr-major', action="store_true",
                                 help="increment major in version. Defaults to false.")
        self.parser.add_argument('-sp', '--skip-push', action="store_true",
                                 help="skip the push step. Defaults to false.'")
        self.parser.add_argument('-v', '--verbose', help="verbose mode for debugging. Defaults to false.", action="store_true")
        self.parser.add_argument('-f', '--force-push', action="store_true",
                                 help="force push. Not recommended. Forces push even if validation checks failed. Applies only if skip_push is false. Defaults to false.")
        self.parser.add_argument('-p', '--incr-patch', action="store_true",
                                 help="increment patch in version. Defaults to false.'")
        self.parser.add_argument('-S', '--secrets-file',
                                 help="specifies an optional secrets file for deployment runtime variables.")
        # (vmahedia) todo Changing this name is slightly more complicated, so making it more verbose for now
        self.parser.add_argument('-d', '--directory',
                                 help="App Repo will be checked out here, this is the working dir CLI will use."
                                      "A temporary directory is created if no directory specified."
                                      "Example: '/home/vagrant/work_dir'.")
        self.parser.add_argument('application', metavar='application', help="application to deploy. \
                                 Can also push specific containers(comma seperated). Example: 'all' \
                                 or 'app1:app2' or 'kairos' or 'app_name[container1,container2]' \
                                 or'app1[container1,container2]:app2[container3,container4]' or 'app1:app2[container]'")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="Path to a Roger configuration file. This can either be an absolute "
                                      "path or a relative path that is taken relative to the ROGER_CONFIG_DIR "
                                      "environment variable.")

        return self.parser

    def main(self, settingObject, appObject, frameworkUtilsObject, gitObj, hooksObj, args):
        try:
            function_execution_start_time = datetime.now()
            execution_result = 'SUCCESS'
            settingObj = settingObject
            appObj = appObject
            config_dir = settingObj.getConfigDir()
            root = settingObj.getCliDir()
            roger_env = appObj.getRogerEnv(config_dir)
            config = appObj.getConfig(config_dir, args.config_file)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            if 'registry' not in roger_env:
                raise ValueError('Registry not found in roger-mesos-tools.config file.')
            else:
                self.registry = roger_env['registry']

            # Setup for Slack-Client, token, and git user
            # (vmahedia) todo: ExtractClass Notifications, it should know who all to notify on what event
            # Event should be registered and SlackNotification should be one of the members. it can have
            # N notifications on a particular "event", Notifications.Notify will broadcast notification to
            # all the interested parties.
            if 'notifications' in config:
                self.slack = Slack(config['notifications'],
                                   '/home/vagrant/.roger_cli.conf.d/slack_token')

            self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.application)

            apps = []
            apps_container_dict = {}
            if args.application == 'all':
                apps = config['apps'].keys()
            else:
                if ":" not in args.application and "[" not in args.application:
                    apps.append(args.application)
                else:
                    for item in args.application.split(":"):
                        if '[' in item:
                            matchObj = re.match(r'(.*)\[(.*)\]', item)
                            apps.append(matchObj.group(1))
                            apps_container_dict[matchObj.group(1)] = matchObj.group(2)
                        else:
                            apps.append(item)

            common_repo = config.get('repo', '')
            environment = roger_env.get('default_environment', '')

            work_dir = ''
            if args.directory:
                work_dir = args.directory
                temp_dir_created = False
                if args.verbose:
                    print("Using {0} as the working directory".format(work_dir))
            else:
                work_dir = mkdtemp()
                temp_dir_created = True
                if args.verbose:
                    print("Created a temporary dir: {0}".format(work_dir))

            if args.environment is None:
                if "ROGER_ENV" in os.environ:
                    env_var = os.environ.get('ROGER_ENV')
                    if env_var.strip() == '':
                        print(
                            "Environment variable $ROGER_ENV is not set. Using the default set from roger-mesos-tools.config file")
                    else:
                        print(
                            "Using value {} from environment variable $ROGER_ENV".format(env_var))
                        environment = env_var
            else:
                environment = args.environment

            if environment not in roger_env['environments']:
                self.removeDirTree(work_dir, args, temp_dir_created)
                raise ValueError('Environment not found in roger-mesos-tools.config file.')

            branch = "master"  # master by default
            if args.branch is not None:
                branch = args.branch

            try:
                for app in apps:
                    if app not in config['apps']:
                        raise ValueError('Application {} specified not found.'.format(app))
                    else:
                        try:
                            if args.verbose:
                                print("Deploying {} ...".format(app))
                            self.deployApp(settingObject, appObject, frameworkUtilsObject, gitObj, hooksObj,
                                           root, args, config, roger_env, work_dir, config_dir, environment, app, branch, self.slack, args.config_file, common_repo, temp_dir_created, apps_container_dict)
                        except (IOError, ValueError) as e:
                            error_msg = "Error when deploying {}: {}".format(app, repr(e))
                            printErrorMsg(error_msg)
                            pass    # try deploying the next app
            except (Exception) as e:
                printException(e)
                raise
        except (Exception) as e:
            execution_result = 'FAILURE'
            printException(e)
            raise
        finally:
            # Check if the initializition of variables carried out
            if 'function_execution_start_time' not in globals() and 'function_execution_start_time' not in locals():
                function_execution_start_time = datetime.now()

            if 'execution_result' not in globals() and 'execution_result' not in locals():
                execution_result = 'FAILURE'

            if 'config_name' not in globals() and 'config_name' not in locals():
                config_name = ""

            if 'environment' not in globals() and 'environment' not in locals():
                environment = "dev"

            if not hasattr(args, "application"):
                args.application = ""

            if 'settingObj' not in globals() and 'settingObj' not in locals():
                settingObj = Settings()

            if 'work_dir' not in globals() and 'work_dir' not in locals():
                work_dir = ''
                temp_dir_created = False

            if not (self.rogerGitPullObject.outcome is 1 and self.rogerBuildObject.outcome is 1 and self.rogerPushObject.outcome is 1):
                execution_result = 'FAILURE'

            try:
                # If the deploy fails before going through any steps
                sc = self.utils.getStatsClient()
                if not hasattr(self, "identifier"):
                    self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.application)
                args.application = self.utils.extract_app_name(args.application)
                time_take_milliseonds = ((datetime.now() - function_execution_start_time).total_seconds() * 1000)
                input_metric = "roger-tools.rogeros_tools_exec_time," + "app_name=" + str(args.application) + ",event=deploy" + ",outcome=" + str(execution_result) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser()) + ",identifier=" + str(self.identifier)
                tup = (input_metric, time_take_milliseonds)
                self.statsd_message_list.append(tup)
                self.removeDirTree(work_dir, args, temp_dir_created)
            except (Exception) as e:
                error_msg = "Error when deploying {}: {}".format(app, repr(e))
                printErrorMsg(error_msg)
                raise

    def deployApp(self, settingObject, appObject, frameworkUtilsObject, gitObj, hooksObj, root, args, config,
                  roger_env, work_dir, config_dir, environment, app, branch, slack, config_file, common_repo, temp_dir_created, apps_container_dict):

        startTime = datetime.now()
        settingObj = settingObject
        appObj = appObject
        frameworkUtils = frameworkUtilsObject
        environmentObj = roger_env['environments'][environment]
        data = appObj.getAppData(config_dir, config_file, app)
        frameworkObj = frameworkUtils.getFramework(data)
        framework = frameworkObj.getName()

        repo = ''
        if common_repo != '':
            repo = data.get('repo', common_repo)
        else:
            repo = data.get('repo', app)

        image_name = ''
        image = ''

        skip_gitpull = True if args.skip_gitpull else False

        # get/update target source(s)
        if not skip_gitpull:
            args.app_name = app
            args.directory = work_dir
            self.rogerGitPullObject.statsd_message_list = self.statsd_message_list
            self.rogerGitPullObject.identifier = self.identifier
            self.rogerGitPullObject.main(settingObj, appObj, gitObj, hooksObj, args)

        skip_build = True if args.skip_build else False
        skip_push = True if args.skip_push else False
        secrets_file = args.secrets_file if args.secrets_file else None

        # Set initial version
        # todo (vmahedia) #image_name naming should not be magic, make it explicit

        # todo (vmahedia) ExtractClass GitInfo, no need to pass args, we already have the information.
        # We deal with only one repo at a time. It may change in future but we can change the code then.
        image_git_sha = getGitSha(work_dir, repo, branch, gitObj)
        image_name = "{0}-{1}-{2}/v0.1.0".format(config['name'], app, image_git_sha)
        print(colored("******Fetching current version deployed or latest version from registry.\
                       This is used to bump to next version.******", "grey"))
        if skip_build:
            curr_image_ver = frameworkObj.getCurrentImageVersion(
                roger_env, environment, app)
            self.image_name = curr_image_ver

            if args.verbose:
                print("Current image version deployed on {0} is :{1}".format(framework, curr_image_ver))
            if curr_image_ver is not None:
                image_name = "{0}-{1}-{2}".format(
                    config['name'], app, curr_image_ver)
                if args.verbose:
                    print("Image current version from {0} endpoint is:{1}".format(framework, image_name))
            else:
                if args.verbose:
                    print("Using base version for image:{0}".format(image_name))
        else:
            # Docker build,tag and push
            image_name = self.getNextVersion(
                config, roger_env, app, branch, work_dir, repo, args, gitObj)
            print(colored("******Done finding latest version******", "green"))
            image_name = "{0}-{1}-{2}".format(config['name'], app, image_name)
            print(colored("Bumped up image to version:{0}".format(image_name), "green"))
            self.image_name = image_name
            build_args = args
            build_args.app_name = app
            build_args.directory = os.path.abspath(work_dir)
            build_args.tag_name = image_name
            build_args.config_file = config_file
            build_args.env = environment
            build_args.push = True
            build_args.verbose = args.verbose
            try:
                self.rogerBuildObject.identifier = self.identifier
                self.rogerBuildObject.statsd_message_list = self.statsd_message_list
                self.rogerBuildObject.main(settingObj, appObject, hooksObj,
                                           self.dockerUtilsObject, self.dockerObject, build_args)
            except ValueError:
                raise

        print("Image Version is: {}".format(colored(image_name, "cyan")))

        # Deploying the app to framework
        args.image_name = image_name
        args.config_file = config_file
        args.env = environment
        if app in apps_container_dict:
            args.app_name = str(app) + ":" + apps_container_dict[app]
        else:
            args.app_name = app
        self.rogerPushObject.identifier = self.identifier
        self.rogerPushObject.statsd_message_list = self.statsd_message_list
        self.rogerPushObject.main(settingObj, appObj, frameworkUtils,
                                  hooksObj, args)

        deployTime = datetime.now() - startTime

        username = settingObj.getUser()

        deployMessage = "{0}'s deploy for {1} / {2} / {3} completed in {4} seconds.".format(
            username, app, environment, branch, deployTime.total_seconds())
        if slack is not None:
            slack.api_call(deployMessage)
        print(colored(deployMessage, "green"))


if __name__ == "__main__":

    roger_deploy = RogerDeploy()
    roger_deploy.parser = roger_deploy.parseArgs()
    args = roger_deploy.parser.parse_args()
    if args.skip_gitpull and not args.directory:
        printErrorMsg("Define 'directory' arg, dir where app repo is checked out, needed to deploy "
                      "or remove skip_gitpull flag, in which case a tmp dir will be created to "
                      "checkout the app repo and app will be built and deployed from repo under tmp dir.")
        sys.exit(-1)

    gitObj = GitUtils()
    settingObj = Settings()
    appObj = AppConfig()

    frameworkUtils = FrameworkUtils()
    hooksObj = Hooks()
    roger_deploy.main(settingObj, appObj, frameworkUtils,
                      gitObj, hooksObj, args)
    result_list = []
    tools_version_value = roger_deploy.utils.get_version()
    image_name = roger_deploy.registry + "/" + roger_deploy.image_name
    image_tag_value = urllib.quote("'" + image_name + "'")
    try:
        for task_id_value in roger_deploy.rogerPushObject.task_id:
            statsd_message_list = roger_deploy.utils.append_arguments(roger_deploy.statsd_message_list, task_id=task_id_value, tools_version=tools_version_value, image_tag=image_tag_value)
            result_list.append(statsd_message_list)

        sc = roger_deploy.utils.getStatsClient()

        for lst in result_list:
            for item in lst:
                sc.timing(item[0], item[1])

        for item in roger_deploy.rogerPushObject.statsd_push_list:
            sc.timing(item[0], item[1])

    except (Exception) as e:
        error_msg = "Error when deploying {}: {}".format(app, repr(e))
        printErrorMsg(error_msg)
