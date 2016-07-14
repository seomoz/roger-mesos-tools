#!/usr/bin/python

from __future__ import print_function
import argparse
import json
import os
import sys
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.hooks import Hooks
from cli.utils import Utils
from cli.dockerutils import DockerUtils
from cli.docker_build import Docker
from datetime import datetime

import contextlib
import statsd


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

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger build', description=describe())
        self.parser.add_argument('app_name', metavar='app_name',
                                 help="application to build. Example: 'agora'.")
        self.parser.add_argument('directory', metavar='directory',
                                 help="working directory. Example: '/home/vagrant/work_dir'.")
        self.parser.add_argument('tag_name', metavar='tag_name',
                                 help="tag for the built image. Example: 'roger-collectd:0.20'.")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="configuration file to use. Example: 'content.json'.")
        self.parser.add_argument(
            '--push', '-p', help="Also push to registry. Defaults to false.", action="store_true")
        return self.parser

    def main(self, settingObj, appObj, hooksObj, dockerUtilsObj, dockerObj, args):
        try:
            function_execution_start_time = datetime.now()
            execution_result = 'SUCCESS'  # Assume the execution_result to be SUCCESS unless exception occurs
            config_dir = settingObj.getConfigDir()
            root = settingObj.getCliDir()
            config = appObj.getConfig(config_dir, args.config_file)
            roger_env = appObj.getRogerEnv(config_dir)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            common_repo = config.get('repo', '')
            if not hasattr(args, "env"):
                args.env = ""
            data = appObj.getAppData(config_dir, args.config_file, args.app_name)
            if not data:
                raise ValueError('Application with name [{}] or data for it not found at {}/{}.'.format(
                    args.app_name, config_dir, args.config_file))
            repo = ''
            if common_repo != '':
                repo = data.get('repo', common_repo)
            else:
                repo = data.get('repo', args.app_name)

            projects = data.get('privateProjects', ['none'])
            projects = ','.join(projects)
            docker_path = data.get('path', 'none')

            # get/update target source(s)
            file_exists = True
            file_path = ''
            cur_dir = ''
            if "PWD" in os.environ:
                cur_dir = os.environ.get('PWD')
            abs_path = os.path.abspath(args.directory)
            repo_name = appObj.getRepoName(repo)
            if docker_path != 'none':
                if abs_path == args.directory:
                    file_path = "{0}/{1}/{2}".format(args.directory,
                                                     repo_name, docker_path)
                else:
                    file_path = "{0}/{1}/{2}/{3}".format(
                        cur_dir, args.directory, repo_name, docker_path)
            else:
                if abs_path == args.directory:
                    file_path = "{0}/{1}".format(args.directory, repo_name)
                else:
                    file_path = "{0}/{1}/{2}".format(cur_dir,
                                                     args.directory, repo_name)

            if not hasattr(args, "app_name"):
                args.app_name = ""

            if not hasattr(self, "identifier"):
                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)

            args.app_name = self.utils.extract_app_name(args.app_name)
            hookname = "pre_build"
            hookname_input_metric = "roger-tools.rogeros_deployment," + "event=" + hookname + ",app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(args.env) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, file_path, hookname_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))

            build_filename = 'Dockerfile'

            if 'build_filename' in data:
                build_filename = ("{0}/{1}".format(file_path, data['build_filename']))
                file_exists = os.path.exists(build_filename)
                if not file_exists:
                    raise ValueError("Specified build file: {} does not exist. Exiting build.".format(build_filename))
            else:
                file_exists = os.path.exists("{0}/Dockerfile".format(file_path))

            if file_exists:
                if 'registry' not in roger_env:
                    raise ValueError('Registry not found in roger-mesos-tools.config file.')
                image = "{0}/{1}".format(roger_env['registry'], args.tag_name)
                try:
                    if abs_path == args.directory:
                        try:
                            dockerObj.docker_build(
                                dockerUtilsObj, appObj, args.directory, repo, projects, docker_path, image, build_filename)
                        except ValueError:
                            print('Docker build failed.')
                            raise
                    else:
                        directory = '{0}/{1}'.format(cur_dir, args.directory)
                        try:
                            dockerObj.docker_build(
                                dockerUtilsObj, appObj, directory, repo, projects, docker_path, image, build_filename)
                        except ValueError:
                            print('Docker build failed.')
                            raise
                    build_message = "Image {0} built".format(image)
                    if(args.push):
                        exit_code = dockerUtilsObj.docker_push(image)
                        if exit_code != 0:
                            raise ValueError(
                                'Docker push failed.')
                        build_message += " and pushed to registry {}".format(roger_env[
                                                                             'registry'])
                    print(build_message)
                except (IOError) as e:
                    print("The folowing error occurred.(Error: %s).\n" %
                          e, file=sys.stderr)
                    raise
            else:
                print("Dockerfile does not exist in dir: {}".format(file_path))

            hookname = "post_build"
            hookname_input_metric = "roger-tools.rogeros_deployment," + "event=" + hookname + ",app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(args.env) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, file_path, hookname_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))
        except (Exception) as e:
            execution_result = 'FAILURE'
            print("The following error occurred: %s" %
                  e, file=sys.stderr)
            raise
        finally:
            try:
                # If the build fails before going through any steps
                if 'function_execution_start_time' not in globals() and 'function_execution_start_time' not in locals():
                    function_execution_start_time = datetime.now()

                if 'execution_result' not in globals() and 'execution_result' not in locals():
                    execution_result = 'FAILURE'

                if 'config_name' not in globals() and 'config_name' not in locals():
                    config_name = ""

                if 'environment' not in globals() and 'environment' not in locals():
                    environment = "dev"

                if not hasattr(args, "env"):
                    args.env = "dev"

                if not hasattr(args, "app_name"):
                    args.app_name = ""

                if 'settingObj' not in globals() and 'settingObj' not in locals():
                    settingObj = Settings()

                sc = self.utils.getStatsClient()
                if not hasattr(self, "identifier"):
                    self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)
                time_take_milliseonds = ((datetime.now() - function_execution_start_time).total_seconds() * 1000)
                input_metric = "roger-tools.rogeros_deployment," + "app_name=" + str(args.app_name) + ",event=build" + ",identifier=" + str(self.identifier) + ",outcome=" + str(execution_result) + ",config_name=" + str(config_name) + ",env=" + str(args.env) + ",user=" + str(settingObj.getUser())
                sc.timing(input_metric, time_take_milliseonds)
            except (Exception) as e:
                print("The following error occurred: %s" %
                      e, file=sys.stderr)
                raise


if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    hooksObj = Hooks()
    dockerUtilsObj = DockerUtils()
    dockerObj = Docker()
    roger_build = RogerBuild()
    roger_build.parser = roger_build.parse_args()
    args = roger_build.parser.parse_args()
    roger_build.main(settingObj, appObj, hooksObj,
                     dockerUtilsObj, dockerObj, args)
