#!/usr/bin/python

from __future__ import print_function
import argparse
import json
import os
import sys
import shlex
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.hooks import Hooks
from cli.utils import Utils
from cli.utils import printException, printErrorMsg
from cli.dockerutils import DockerUtils
from cli.docker_build import Docker
from termcolor import colored
from datetime import datetime

import contextlib
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
    return 'runs the docker build and optionally pushes it into the registry.'


class RogerBuild(object):

    def __init__(self):
        self.utils = Utils()
        self.outcome = 1
        self.registry = ""
        self.tag_name = ""

    def parse_args(self):
        self.parser = argparse.ArgumentParser(prog='roger build', description=describe())
        self.parser.add_argument('app_name', metavar='app_name',
                                 help="application to build. Example: 'agora'.")
        self.parser.add_argument('directory', metavar='directory',
                                 help="App Repo will be checked out here, this is the working dir CLI will use."
                                      "A temporary directory is created if no directory specified."
                                      "Example: '/home/vagrant/work_dir'.")
        self.parser.add_argument('tag_name', metavar='tag_name',
                                 help="tag for the built image. Example: 'roger-collectd:0.20'.")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="configuration file to use. Example: 'content.json'.")
        self.parser.add_argument('-v', '--verbose', help="verbose mode for debugging. Defaults to false.", action="store_true")
        self.parser.add_argument('--push', '-p', help="Also push to registry. Defaults to false.", action="store_true")
        self.parser.add_argument('--build-arg', action='append',
                                 help='docker build-arg; Use flags multiple times to pass more than one arg')
        self.parser.add_argument('-ns', '--disable-swaparoo', help="Disables swaparoo functionality", action="store_true")
        return self.parser

    def main(self, settingObj, appObj, hooksObj, dockerUtilsObj, dockerObj, args):
        print(colored("******Building the Docker image now******", "grey"))
        try:
            config_dir = settingObj.getConfigDir()
            root = settingObj.getCliDir()
            config = appObj.getConfig(config_dir, args.config_file)
            hooksObj.config_file = args.config_file
            roger_env = appObj.getRogerEnv(config_dir)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            common_repo = config.get('repo', '')
            if not hasattr(args, "env"):
                args.env = "dev"
            data = appObj.getAppData(config_dir, args.config_file, args.app_name)
            if not data:
                raise ValueError("Application with name [{}] or data for it not found at {}/{}.".format(
                    args.app_name, config_dir, args.config_file))
            repo = ''
            if common_repo != '':
                repo = data.get('repo', common_repo)
            else:
                repo = data.get('repo', args.app_name)

            docker_build_args = {}

            if 'build-args' in data:
                if 'environment' in data['build-args']:
                    if args.env in data['build-args']['environment']:
                        docker_build_args = data['build-args']['environment'][args.env]

            # read the build-args from commandline like docker does as well
            # build-args defined on command line will override the ones from the config file, for the same keys
            # so this update of dictionary has to be done after we have read build arg values from the config file
            if args.build_arg:
                docker_build_args.update(dict(arg_key_val_str.split('=') for arg_key_val_str in args.build_arg))

            projects = data.get('privateProjects', [])


            # get/update target source(s)
            file_exists = True
            file_path = ''
            cur_dir = ''
            if "PWD" in os.environ:
                cur_dir = os.environ.get('PWD')


            # This is bad code, assuming current directory and then trying to again guess, this is not rocket science
            # it's a fucking file path, as simple as that. https://seomoz.atlassian.net/browse/ROGER-2405
            # dockerfile location possibilities
            #    1. Path relative to the repo, we know repo path for cli is <checkout_dir>/<repo>
            #    2. Absolute path
            # This path comes from config file and not passed on commandline so we should not try to prefix current
            # working directory if the relative path is passed, don't try to guess too much.
            # changelog : relative path from current directory won't work for working_directory or checkout_dir
            # changelog : working_directory or checkout_dir should be absolute path, not backward-compatible
            checkout_dir = os.path.abspath(args.directory)
            repo_name = appObj.getRepoName(repo)
            # (vmahedia) todo : this should be called docker_file_dir
            dockerfile_rel_repo_path = data.get('path', '')
            file_path = os.path.join(checkout_dir, repo_name, dockerfile_rel_repo_path)


            if not hasattr(args, "app_name"):
                args.app_name = ""

            if not hasattr(self, "identifier"):
                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)

            args.app_name = self.utils.extract_app_name(args.app_name)
            hookname = "pre_build"
            exit_code = hooksObj.run_hook(hookname, data, file_path, args.env, settingObj.getUser())
            if exit_code != 0:
                raise ValueError("{} hook failed.".format(hookname))

            build_filename = 'Dockerfile'

            if 'build_filename' in data:
                build_filename = ("{0}/{1}".format(file_path, data['build_filename']))
                file_exists = os.path.exists(build_filename)
                if not file_exists:
                    raise ValueError("Specified build file: {} does not exist. Exiting build.".format(build_filename))
            else:
                file_exists = os.path.exists("{0}/Dockerfile".format(file_path))

            if file_exists:
                # (vmahedia) todo: We know what parameters are required for build command so we should not wait until
                # now to bailout. Config parser should have a validator for every command to see if all the Required
                # parameters are passed or not. Why do all this up to this point if we know we will fail on this.
                # RequiredParameter, below, "registry"
                if 'registry' not in roger_env:
                    raise ValueError("Registry not found in roger-mesos-tools.config file.")
                else:
                    self.registry = roger_env['registry']
                self.tag_name = args.tag_name
                image = "{0}/{1}".format(roger_env['registry'], args.tag_name)
                try:
                    if checkout_dir == args.directory:
                        try:
                            dockerObj.docker_build(
                                dockerUtilsObj, appObj, args.directory, repo, projects, dockerfile_rel_repo_path, image, docker_build_args, args.verbose, build_filename, args.disable_swaparoo)
                        except ValueError:
                            raise ValueError("Docker build failed")
                    else:
                        directory = os.path.join(cur_dir, args.directory)
                        try:
                            dockerObj.docker_build(
                                dockerUtilsObj, appObj, directory, repo, projects, dockerfile_rel_repo_path, image, docker_build_args, args.verbose, build_filename, args.disable_swaparoo)
                        except ValueError:
                            print('Docker build failed.')
                            raise
                    print(colored("******Successfully built Docker image******", "green"))
                    build_message = "Image [{}]".format(image)
                    if(args.push):
                        print(colored("******Pushing Docker image to registry******", "grey"))
                        exit_code = dockerUtilsObj.docker_push(image, args.verbose)
                        if exit_code != 0:
                            raise ValueError(
                                'Docker push failed.')
                        build_message += " successfully pushed to registry [{}]*******".format(roger_env[
                                                                             'registry'])
                    print(colored(build_message, "green"))
                except (IOError) as e:
                    printException(e)
                    raise
            else:
                print(colored("Dockerfile does not exist in dir: {}".format(file_path), "red"))

            hookname = "post_build"
            exit_code = hooksObj.run_hook(hookname, data, file_path, args.env, settingObj.getUser())
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))
        except (Exception) as e:
            printException(e)
            raise
        finally:
            # todo: maybe send a datadog event? 
            pass

if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    hooksObj = Hooks()
    dockerUtilsObj = DockerUtils()
    dockerObj = Docker()
    roger_build = RogerBuild()
    roger_build.parser = roger_build.parse_args()
    args = roger_build.parser.parse_args()
    try:
        roger_build.main(settingObj, appObj, hooksObj, dockerUtilsObj, dockerObj, args)
    except (Exception) as e:
        printException(e)
