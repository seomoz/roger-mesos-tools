#!/usr/bin/python

from __future__ import print_function
import argparse
from jinja2 import Environment, FileSystemLoader, StrictUndefined, exceptions
from datetime import datetime
import requests
import json
import os
import sys
import traceback
import logging
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.utils import Utils
from cli.marathon import Marathon
from cli.hooks import Hooks
from cli.chronos import Chronos
from cli.frameworkUtils import FrameworkUtils
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
    return 'pushes the application into roger mesos.'


class RogerPush(object):

    def __init__(self):
        self.utils = Utils()

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger push', description=describe())
        self.parser.add_argument('app_name', metavar='app_name', help="application to push. Can also push specific"
                                 " containers(comma seperated). Example: 'agora' or 'app_name:container1,container2'")
        self.parser.add_argument('-e', '--env', metavar='env',
                                 help="environment to push to. Example: 'dev' or 'prod'")
        self.parser.add_argument('directory', metavar='directory',
                                 help="working directory. Example: '/home/vagrant/work_dir'")
        self.parser.add_argument('image_name', metavar='image_name',
                                 help="image name that includes version to use. Example: 'roger-collectd-v0.20' or 'elasticsearch-v0.07'")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="configuration file to use. Example: 'content.json' or 'kwe.json'")
        self.parser.add_argument(
            '--skip-push', '-s', help="skips push. Only generates components for review. Defaults to false.", action="store_true")
        self.parser.add_argument(
            '--force-push', '-f', help="force push. Not Recommended. Forces push even if validation checks failed. Defaults to false.", action="store_true")
        self.parser.add_argument('--secrets-file', '-S',
                                 help="specifies an optional secrets file for deploy runtime variables.")
        return self.parser

    def loadSecrets(self, secrets_dir, file_name, args, environment):
        if args.secrets_file is not None:
            print("Using specified secrets file: {}".format(args.secrets_file))
            file_name = args.secrets_file
        exists = os.path.exists(secrets_dir)
        if exists is False:
            os.makedirs(secrets_dir)

        # Two possible paths -- first without environment, second with
        path1 = "{}/{}".format(secrets_dir, file_name)
        path2 = "{}/{}/{}".format(secrets_dir, environment, file_name)
        print(" Loading secrets from {} or {}".format(path1, path2))

        try:
            with open(path1) as f:
                return_file = yaml.load(f) if path1.lower().endswith('.yml') else json.load(f)
            return return_file
        except IOError:
            pass
        except ValueError as e:
            raise ValueError(
                " Error while loading json from {} - {}".format(path1, e))

        try:
            with open(path2) as f:
                return_file = yaml.load(f) if path2.lower().endswith('.yml') else json.load(f)
            return return_file
        except IOError:
            print(" Couldn't load secrets file environment in %s or %s\n" %
                  (path1, path2), file=sys.stderr)
            return {}
        except ValueError as e:
            raise ValueError(
                " Error while loading json from {} - {}".format(path2, e))

    def replaceSecrets(self, output_dict, secrets_dict):
        if type(output_dict) is not dict:
            return output_dict

        for key in output_dict:
            if output_dict[key] == "SECRET":
                if key in secrets_dict.keys():
                    output_dict[key] = secrets_dict[key]

            if type(output_dict[key]) is list:
                temp_list = []
                for list_elem in output_dict[key]:
                    temp_list.append(self.replaceSecrets(
                        list_elem, secrets_dict))
                    output_dict[key] = temp_list

            if type(output_dict[key]) is dict:
                temp_dict = self.replaceSecrets(output_dict[key], secrets_dict)
                output_dict[key] = temp_dict

        return output_dict

    def mergeSecrets(self, json_str, secrets):
        '''Given a JSON string and an object of secret environment variables, replaces
        parses the JSON keys with the secret variables. Returns back
        a JSON string. Raises an error if there are any SECRET variables still exists.'''
        print("WARNING - The use of \"SECRET\" is deprecated. Please switch to using Jinja variables. To do so,"
              " use '{{ <actual variable name> }}' instead of \"SECRET\" in the target file.")
        output_dict = json.loads(json_str)
        json_str = json.dumps(self.replaceSecrets(
            output_dict, secrets), indent=4)

        if '\"SECRET\"' in json_str:
            print('There are still "SECRET" values -- does your secrets file have all secret environment variables?')
            return "StandardError"
        return json_str

    def renderTemplate(self, template, environment, image, app_data, config, container, container_name, additional_vars):

        variables = {'environment': environment, 'image': image}

        # Copy variables from config-wide, app-wide, then container-wide variable
        # configs, each one from "global" and then environment-specific.
        for obj in [config, app_data, container]:
            if type(obj) == dict and 'vars' in obj:
                variables.update(obj['vars'].get('global', {}))
                variables.update(obj['vars'].get('environment', {}).get(environment, {}))

        variables.update(additional_vars)

        return template.render(variables)

    def repo_relative_path(self, appConfig, args, repo, path):
        '''Returns a path relative to the repo, assumed to be under [args.directory]/[repo name]'''
        repo_name = appConfig.getRepoName(repo)
        abs_path = os.path.abspath(args.directory)
        if abs_path == args.directory:
            return "{0}/{1}/{2}".format(args.directory, repo_name, path)
        else:
            return "{0}/{1}/{2}/{3}".format(os.environ.get('PWD', ''),
                                            args.directory, repo_name, path)

    def main(self, settings, appConfig, frameworkObject, hooksObj, args):
        try:
            settingObj = settings
            appObj = appConfig
            frameworkUtils = frameworkObject
            config_dir = settingObj.getConfigDir()
            cur_file_path = os.path.dirname(os.path.realpath(__file__))
            config = appObj.getConfig(config_dir, args.config_file)
            config_name = ""
            if 'name' in config:
                config_name = config['name']
            roger_env = appObj.getRogerEnv(config_dir)

            if 'registry' not in roger_env.keys():
                raise ValueError(
                    'Registry not found in roger-mesos-tools.config file.')

            environment = roger_env.get('default_environment', '')
            if args.env is None:
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
                environment = args.env

            if environment not in roger_env['environments']:
                raise ValueError(
                    'Environment not found in roger-mesos-tools.config file.')

            environmentObj = roger_env['environments'][environment]
            common_repo = config.get('repo', '')
            app_name = args.app_name
            container_list = []
            if ':' in app_name:
                tokens = app_name.split(':')
                app_name = tokens[0]
                if ',' in tokens[1]:
                    container_list = tokens[1].split(',')
                else:
                    container_list.append(tokens[1])

            data = appObj.getAppData(config_dir, args.config_file, app_name)
            if not data:
                raise ValueError('Application with name [{}] or data for it not found at {}/{}.'.format(
                    app_name, config_dir, args.config_file))

            configured_container_list = []
            for task in data['containers']:
                if type(task) == dict:
                    configured_container_list.append(task.keys()[0])
                else:
                    configured_container_list.append(task)
            if not set(container_list) <= set(configured_container_list):
                raise ValueError('List of containers [{}] passed do not match list of acceptable containers: [{}]'.format(
                    container_list, configured_container_list))

            frameworkObj = frameworkUtils.getFramework(data)
            framework = frameworkObj.getName()

            repo = ''
            if common_repo != '':
                repo = data.get('repo', common_repo)
            else:
                repo = data.get('repo', app_name)

            comp_dir = settingObj.getComponentsDir()
            templ_dir = settingObj.getTemplatesDir()
            secrets_dir = settingObj.getSecretsDir()

            # template marathon files
            if not container_list:
                data_containers = data['containers']
            else:
                data_containers = container_list

            failed_container_dict = {}

            template = ''
            # Required for when work_dir,component_dir,template_dir or
            # secret_env_dir is something like '.' or './temp"
            os.chdir(cur_file_path)
            app_path = ''
            if 'template_path' in data:
                app_path = self.repo_relative_path(appObj, args, repo, data['template_path'])
            else:
                app_path = templ_dir

            extra_vars = {}
            if 'extra_variables_path' in data:
                ev_path = self.repo_relative_path(appObj, args, repo, data['extra_variables_path'])
                with open(ev_path) as f:
                    extra_vars = yaml.load(f) if ev_path.lower(
                    ).endswith('.yml') else json.load(f)

            if not app_path.endswith('/'):
                app_path = app_path + '/'

            if not hasattr(self, "identifier"):
                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)

            hookname = "pre_push"
            hook_input_metric = "roger-tools." + hookname + "_time," + "app_name=" + str(args.app_name)  + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, app_path, hook_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))

            for container in data_containers:
                if type(container) == dict:
                    container_name = str(container.keys()[0])
                    container = container[container_name]
                    containerConfig = "{0}-{1}.json".format(
                        config['name'], container_name)
                else:
                    container_name = container
                    containerConfig = "{0}-{1}.json".format(
                        config['name'], container)

                env = Environment(loader=FileSystemLoader(
                    "{}".format(app_path)), undefined=StrictUndefined)
                template_with_path = "[{}{}]".format(app_path, containerConfig)
                try:
                    template = env.get_template(containerConfig)
                except exceptions.TemplateNotFound as e:
                    raise ValueError(
                        "The template file {} does not exist".format(template_with_path))
                except Exception as e:
                    raise ValueError(
                        "Error while reading template from {} - {}".format(template_with_path, e))

                additional_vars = {}
                additional_vars.update(extra_vars)
                secret_vars = self.loadSecrets(secrets_dir, containerConfig, args, environment)
                additional_vars.update(secret_vars)

                image_path = "{0}/{1}".format(
                    roger_env['registry'], args.image_name)
                print("Rendering content from template {} for environment [{}]".format(
                    template_with_path, environment))
                try:
                    output = self.renderTemplate(template, environment, image_path, data, config, container, container_name, additional_vars)
                except exceptions.UndefinedError as e:
                    error_str = "The following error occurred. %s.\n" % e
                    print(error_str, file=sys.stderr)
                    failed_container_dict[container_name] = error_str
                    pass

                # Adding check to see if all jinja variables git resolved fot the
                # container
                if container_name not in failed_container_dict:
                    # Adding check so that not all apps try to mergeSecrets
                    try:
                        outputObj = json.loads(output)
                    except Exception as e:
                        raise ValueError(
                            "Error while loading json from {} - {}".format(template_with_path, e))

                    if 'SECRET' in output:
                        output = self.mergeSecrets(output, self.loadSecrets(
                            secrets_dir, containerConfig, args, environment))
                    if output != "StandardError":
                        try:
                            comp_exists = os.path.exists("{0}".format(comp_dir))
                            if comp_exists is False:
                                os.makedirs("{0}".format(comp_dir))
                            comp_env_exists = os.path.exists(
                                "{0}/{1}".format(comp_dir, environment))
                            if comp_env_exists is False:
                                os.makedirs(
                                    "{0}/{1}".format(comp_dir, environment))
                        except Exception as e:
                            logging.error(traceback.format_exc())
                        with open("{0}/{1}/{2}".format(comp_dir, environment, containerConfig), 'wb') as fh:
                            fh.write(output)

            if args.skip_push:
                print("Skipping push to {} framework. The rendered config file(s) are under {}/{}".format(
                    framework, comp_dir, environment))
            else:
                # push to roger framework
                if 'owner' in config:
                    frameworkObj.act_as_user = config['owner']

                for container in data_containers:
                    try:
                        function_execution_start_time = datetime.now()
                        execution_result = 'SUCCESS'  # Assume the execution_result to be SUCCESS unless exception occurs
                        sc = self.utils.getStatsClient()
                    except (Exception) as e:
                        print("The following error occurred: %s" %
                              e, file=sys.stderr)
                    try:
                        if type(container) == dict:
                            container_name = str(container.keys()[0])
                            containerConfig = "{0}-{1}.json".format(
                                config['name'], container_name)
                        else:
                            container_name = container
                            containerConfig = "{0}-{1}.json".format(
                                config['name'], container)

                        if container_name in failed_container_dict:
                            print("Failed push to {} framework for container {} as unresolved Jinja variables present in template.".format(
                                framework, container))
                        else:
                            config_file_path = "{0}/{1}/{2}".format(
                                comp_dir, environment, containerConfig)

                            result = frameworkObj.runDeploymentChecks(
                                config_file_path, environment)

                            if args.force_push or result is True:
                                frameworkObj.put(
                                    config_file_path, environmentObj, container_name, environment)
                            else:
                                print("Skipping push to {} framework for container {} as Validation Checks failed.".format(
                                    framework, container))
                    except (Exception) as e:
                        print("The following error occurred: %s" %
                              e, file=sys.stderr)
                        execution_result = 'FAILURE'
                        raise
                    finally:
                        try:
                            time_take_milliseonds = (( datetime.now() - function_execution_start_time ).total_seconds() * 1000 )
                            input_metric = "roger-tools.roger_push_time," + "app_name=" + str(args.app_name) + ",container_name=" + str(container_name) + ",identifier=" + str(self.identifier) + ",outcome=" + str(execution_result) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
                            sc.timing(input_metric, time_take_milliseonds)
                        except (Exception) as e:
                            print("The following error occurred: %s" %
                                  e, file=sys.stderr)
                            raise

            hookname = "post_push"
            hook_input_metric = "roger-tools." + hookname + "_time," + "app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, app_path, hook_input_metric)
            if exit_code != 0:
                raise ValueError('{} hook failed.'.format(hookname))

        except (Exception) as e:
            print("The following error occurred: %s" %
                  e, file=sys.stderr)
            raise

if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    frameworkUtils = FrameworkUtils()
    hooksObj = Hooks()
    roger_push = RogerPush()
    roger_push.parser = roger_push.parse_args()
    roger_push.args = roger_push.parser.parse_args()
    roger_push.main(settingObj, appObj, frameworkUtils,
                    hooksObj, roger_push.args)
