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
from cli.utils import printException, printErrorMsg
from datetime import datetime
from termcolor import colored
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
        self.outcome = 1

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger gitpull', description=describe())
        self.parser.add_argument('app_name', metavar='app_name',
                                 help="application for which code is to be pulled. Example: 'agora' or 'grafana'")
        self.parser.add_argument('directory', metavar='directory',
                                  help="App Repo will be checked out here, this is the working dir CLI will use."
                                       "A temporary directory is created if no directory specified."
                                       "Example: '/home/vagrant/work_dir'.")
        self.parser.add_argument('-v', '--verbose', help="verbose mode for debugging", action="store_true")
        self.parser.add_argument('-b', '--branch', metavar='branch',
                                 help="git branch to pull code from. Example: 'production' or 'master'. Defaults to master.")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="configuration file to use. Example: 'content.json' or 'kwe.json'")
        return self.parser

    def main(self, settings, appConfig, gitObject, hooksObj, args):
        print(colored("******Executing GIT PULL of application repo******", "grey"))
        try:
            function_execution_start_time = datetime.now()
            environment = "dev"
            if hasattr(args, "environment"):
                environment = args.environment
            settingObj = settings
            appObj = appConfig
            gitObj = gitObject
            config_dir = settingObj.getConfigDir()
            hooksObj.config_file = args.config_file
            config = appObj.getConfig(config_dir, args.config_file)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            common_repo = config.get('repo', '')
            data = appObj.getAppData(config_dir, args.config_file, args.app_name)
            if not data:
                raise ValueError("Application with name [{}] or data for it not found at {}/{}.".format(
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

            hookname = "pre_gitpull"
            exit_code = hooksObj.run_hook(hookname, data, args.directory, args.environment, settingObj.getUser())
            if exit_code != 0:
                raise ValueError("{} hook failed.".format(hookname))

            # get/update target source(s)
            repo_name = appObj.getRepoName(repo)
            path = "{0}/{1}".format(args.directory, repo_name)
            if os.path.isdir(path):
                with chdir(path):
                    exit_code = gitObj.gitPull(branch, args.verbose)
            else:
                with chdir('{0}'.format(args.directory)):
                    exit_code = gitObj.gitShallowClone(repo, branch, args.verbose)

            if exit_code != 0:
                raise ValueError("Gitpull failed.")

            hookname = "post_gitpull"
            exit_code = hooksObj.run_hook(hookname, data, args.directory, args.environment, settingObj.getUser())
            if exit_code != 0:
                raise ValueError("{} hook failed.".format(hookname))
        except (Exception) as e:
            printException(e)
            raise
        finally:
            # todo: maybe send a datadog event?
            pass
        print(colored("******Completed the GIT PULL step successfully******", "green"))

if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    gitObj = GitUtils()
    hooksObj = Hooks()
    roger_gitpull = RogerGitPull()
    roger_gitpull.parser = roger_gitpull.parse_args()
    args = roger_gitpull.parser.parse_args()
    try:
        roger_gitpull.main(settingObj, appObj, gitObj, hooksObj, args)
    except (Exception) as e:
        printException(e)
