#!/usr/bin/python

from __future__ import print_function
import argparse
import json
import os
import sys
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.gitutils import GitUtils
from cli.hooks import Hooks
from cli.utils import Utils
from datetime import datetime
import errno

import contextlib


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
    return 'pulls code from the application git repository (clones the repository).'


class RogerGitPull(object):

    def __init__(self):
        self.utils = Utils()

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger gitpull', description=describe())
        self.parser.add_argument('app_name', metavar='app_name',
                                 help="application for which code is to be pulled. Example: 'agora' or 'grafana'")
        self.parser.add_argument('directory', metavar='directory',
                                 help="working directory. The repo has its own directory it this. Example: '/home/vagrant/work_dir'")
        self.parser.add_argument('-b', '--branch', metavar='branch',
                                 help="git branch to pull code from. Example: 'production' or 'master'. Defaults to master.")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="configuration file to use. Example: 'content.json' or 'kwe.json'")
        return self.parser

    def main(self, settings, appConfig, gitObject, hooksObj, args):
        try:
            function_execution_start_time = datetime.now()
            execution_result = 'SUCCESS'  # Assume the execution_result to be SUCCESS unless exception occurs
            environment = "dev"
            if hasattr(args, "environment"):
                environment = args.environment
            settingObj = settings
            appObj = appConfig
            gitObj = gitObject
            config_dir = settingObj.getConfigDir()
            config = appObj.getConfig(config_dir, args.config_file)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            common_repo = config.get('repo', '')
            data = appObj.getAppData(config_dir, args.config_file, args.app_name)
            if not data:
                raise ValueError('Application with name [{}] or data for it not found at {}/{}.'.format(
                    args.app_name, config_dir, args.config_file))
            repo = ''
            if common_repo != '':
                repo = data.get('repo', common_repo)
            else:
                repo = data.get('repo', args.app_name)

            branch = "master"  # master by default
            if args.branch is not None:
                branch = args.branch

            if not os.path.exists(args.directory):
                try:
                    os.makedirs(args.directory)
                except OSError as exception:
                    if exception.errno != errno.EEXIST:
                        raise

            if not hasattr(args, "app_name"):
                args.app_name = ""

            if not hasattr(self, "identifier"):
                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)

            args.app_name = self.utils.verify_app_name(args.app_name)
            hookname = "pre_gitpull"
            hookname_input_metric = "roger-tools.rogeros_deployment," + "event=" + hookname + ",app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, args.directory, hookname_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))

            # get/update target source(s)
            repo_name = appObj.getRepoName(repo)
            path = "{0}/{1}".format(args.directory, repo_name)
            if os.path.isdir(path):
                with chdir(path):
                    exit_code = gitObj.gitPull(branch)
            else:
                with chdir('{0}'.format(args.directory)):
                    exit_code = gitObj.gitShallowClone(repo, branch)

            if exit_code != 0:
                raise ValueError('gitpull failed.')

            hookname = "post_gitpull"
            hookname_input_metric = "roger-tools.rogeros_deployment," + "event=" + hookname + ",app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, args.directory, hookname_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))
        except (Exception) as e:
            print("The following error occurred: %s" %
                  e, file=sys.stderr)
            execution_result = 'FAILURE'
            raise
        finally:
            try:
                # If the gitpull fails before going through any steps
                if 'function_execution_start_time' not in globals() and 'function_execution_start_time' not in locals():
                    function_execution_start_time = datetime.now()

                if 'execution_result' not in globals() and 'execution_result' not in locals():
                    execution_result = 'FAILURE'

                if 'config_name' not in globals() and 'config_name' not in locals():
                    config_name = ""

                if 'environment' not in globals() and 'environment' not in locals():
                    environment = "dev"

                if not hasattr(args, "app_name"):
                    args.app_name = ""

                if 'settingObj' not in globals() and 'settingObj' not in locals():
                    settingObj = Settings()

                sc = self.utils.getStatsClient()
                if not hasattr(self, "identifier"):
                    self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)
                time_take_milliseonds = ((datetime.now() - function_execution_start_time).total_seconds() * 1000)
                input_metric = "roger-tools.rogeros_deployment," + "app_name=" + str(args.app_name) + ",event=gitpull" + ",identifier=" + str(self.identifier) + ",outcome=" + str(execution_result) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
                sc.timing(input_metric, time_take_milliseonds)
            except (Exception) as e:
                print("The following error occurred: %s" %
                      e, file=sys.stderr)
                raise

if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    gitObj = GitUtils()
    hooksObj = Hooks()
    roger_gitpull = RogerGitPull()
    roger_gitpull.parser = roger_gitpull.parse_args()
    args = roger_gitpull.parser.parse_args()
    roger_gitpull.main(settingObj, appObj, gitObj, hooksObj, args)
