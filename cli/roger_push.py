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
import yaml
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.utils import Utils
from cli.utils import printException, printErrorMsg
from cli.marathon import Marathon
from cli.hooks import Hooks
from cli.chronos import Chronos
from cli.frameworkUtils import FrameworkUtils
from datetime import datetime
from termcolor import colored
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
    return 'pushes the application into roger mesos.'


class RogerPush(object):

    def __init__(self):
        self.utils = Utils()
        self.task_id = []
        self.statsd_message_list = []
        self.statsd_push_list = []
        self.outcome = 1
        self.registry = ""
        self.image_name = ""

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger push', description=describe())
        self.parser.add_argument('app_name', metavar='app_name',
                                 help="Name of the App to be pushed, as defined in config file."
                                      "To deploy specific containers from an App, look at example B"
                                      "Example: A. 'agora' B. 'app_name:container1,container2'")
        self.parser.add_argument('-e', '--env', metavar='env',
                                 help="Environment to push to. Example: 'dev' or 'prod'")
        self.parser.add_argument('-v', '--verbose', help="Verbose mode", action="store_false")
        # Changelog: todo - Change this to checkout_dir but it's complicated to make thsi change in other commands
        # so for now, leaving it as it is and will have to take care of this in one change.
        self.parser.add_argument('directory', metavar='directory',
                                 help="App Repo will be checked out here, this is the working dir CLI will use."
                                      "Example: '/home/vagrant/work_dir'")
        self.parser.add_argument('image_name', metavar='image_name',
                                 help="image name that includes version to use."
                                      "Example: 'roger-collectd-v0.20' or 'elasticsearch-v0.07'")
        self.parser.add_argument('config_file', metavar='config_file',
                                 help="Configuration file to use."
                                      "Example: A. 'local.yml' or B.'content.json'")
        self.parser.add_argument('--skip-push', '-s', help="App is not pushed. Only renders template with config."
                                                           "Use it to check generated file before deploying or to debug"
                                                           "Defaults to false.", action="store_true")
        self.parser.add_argument(
            '--force-push', '-f', help="force push. Not Recommended. Forces push even if validation checks failed. Defaults to false.", action="store_true")
        self.parser.add_argument('--secrets-file', '-S',
                                 help="specifies an optional secrets file for deploy runtime variables.")
        return self.parser

    def loadSecrets(self, secrets_dir, file_name, args, environment):
        if args.secrets_file:
            print("Using specified secrets file: {}".format(args.secrets_file))
            file_name = args.secrets_file

        exists = os.path.exists(secrets_dir)
        if exists is False:
            os.makedirs(secrets_dir)

        # (vmahedia) WE SHOULD NOT DO ANY GUESSING GAME BE EXPLICIT
        # about where we expect what and argument should make that very clear to customers
        # Two possible paths -- first without environment, second with
        path1 = "{}/{}".format(secrets_dir, file_name)
        path2 = "{}/{}/{}".format(secrets_dir, environment, file_name)
        secrets_file_paths = [file_name] if os.path.isabs(file_name) else [path1, path2]
        for secrets_file_path in secrets_file_paths:
            if args.verbose:
                print(colored("Trying to load secrets from file {}".format(secrets_file_path), "cyan"))
            try:
                with open(secrets_file_path) as f:
                    return_file = yaml.load(f) if secrets_file_path.lower().endswith('.yml') else json.load(f)
                if args.verbose:
                    print(colored("Loaded secrets from file {}".format(secrets_file_path), "cyan"))
                return return_file
            except IOError:
                if args.verbose:
                    print(colored("Unable to find secrets file {}".format(secrets_file_path), "cyan"))
                pass
            except ValueError as e:
                raise ValueError("Error while loading secrets from {} - {}".format(secrets_file_path, e))

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
        output_dict = json.loads(json_str)
        json_str = json.dumps(self.replaceSecrets(output_dict, secrets), indent=4)

        if '\"SECRET\"' in json_str:
            print(colored("ERROR - Found the \"SECRET\" keyword in the template file -- does your secrets file have all secret environment variables?", "red"))
            print(colored("ERROR - The use of \"SECRET\" is deprecated. Please switch to using Jinja variables. To do so,"
              " use '{{ <actual variable name> }}' instead of \"SECRET\" in the template file.", "red"))
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

    def statsd_counter_logging(self, metric):
        sc = self.utils.getStatsClient()
        sc.incr(metric, 1)

    def repo_relative_path(self, appConfig, args, repo, path):
        '''Returns a path relative to the repo, assumed to be under [args.directory]/[repo name]'''
        repo_name = appConfig.getRepoName(repo)
        abs_path = os.path.abspath(args.directory)
        return os.path.join(args.directory, repo_name, path)


    def getContainerName(self, container):
         return str(container.keys()[0]) if type(container) == dict else container

    def getContainersList(self, app_name):
        container_list = []
        # todo (vmahedia): What does ':' signify? Put explanation.
        if ':' in app_name:
            tokens = app_name.split(':')
            app_name = tokens[0]
            # todo (vmahedia): it's container list - need to explain syntax
            if ',' in tokens[1]:
                container_list = tokens[1].split(',')
            else:
                container_list.append(tokens[1])
        return container_list

    def getConfiguredContainersList(self, app_data):
        configured_container_list = []
        for task in app_data['containers']:
            if type(task) == dict:
                configured_container_list.append(task.keys()[0])
            else:
                configured_container_list.append(task)
        return configured_container_list

    # vmahedia: Why does this have to be so complex? Maybe just define on the commandline explicitly
    def getTargetEnvironment(self, roger_env, args):
        environment = roger_env.get('default_environment', '')
        if args.env is None:
            if "ROGER_ENV" in os.environ:
                env_var = os.environ.get('ROGER_ENV')
                if env_var.strip() == '':
                    print(colored("WARNING - Environment variable $ROGER_ENV is not set. Using the default set "
                                  "from roger-mesos-tools.config file", "yellow"))
                else:
                    if args.verbose:
                        print(colored("Using value {} from environment variable $ROGER_ENV".format(env_var), "grey"))
                    environment = env_var
        else:
            environment = args.env
        return environment

    def getRepository(self, app_data, common_repo, app_name):
        repo = ''
        if common_repo != '':
            repo = app_data.get('repo', common_repo)
        else:
            repo = app_data.get('repo', app_name)
        return repo

    def getAppPath(self, appObj, args, data, repo, templ_dir):
        app_path = ''
        if 'template_path' in data:
            app_path = self.repo_relative_path(appObj, args, repo, data['template_path'])
        else:
            app_path = templ_dir
        return app_path

    def main(self, settings, appConfig, frameworkObject, hooksObj, args):
        print(colored("******Deploying application to framework******", "grey"))
        try:
            validation_failed = False
            settingObj = settings
            appObj = appConfig
            frameworkUtils = frameworkObject
            config_dir = settingObj.getConfigDir()
            hooksObj.config_file = args.config_file
            cur_file_path = os.path.dirname(os.path.realpath(__file__))
            config = appObj.getConfig(config_dir, args.config_file)
            config_name = ""
            act_as_user = ""
            if 'name' in config:
                config_name = config['name']
            if 'act-as' in config:
                act_as_user = config['act-as']
            roger_env = appObj.getRogerEnv(config_dir)

            if not hasattr(args, "app_name"):
                args.app_name = ""

            try:
                self.registry = roger_env['registry']
            except KeyError:
                raise ValueError("Registry not found in roger-mesos-tools.config file.")

            if hasattr(args, "image_name"):
                self.image_name = args.image_name

            environment = self.getTargetEnvironment(roger_env, args)
            # ----------------------------------------------
            # GetEnvironmentConfig(environment)
            # ----------------------------------------------
            try:
                environmentObj = roger_env['environments'][environment]
            except KeyError as e:
                raise ValueError("'environment' not defined in roger-mesos-tools.config file. - {}".format(e))

            data = appObj.getAppData(config_dir, args.config_file, args.app_name)
            if not data:
                raise ValueError("Application with name [{}] or data for it not found at {}/{}.".format(
                                 args.app_name, config_dir, args.config_file))

            container_list = self.getContainersList(args.app_name)
            configured_container_list = self.getConfiguredContainersList(data)

            if not set(container_list) <= set(configured_container_list):
                raise ValueError("List of containers [{}] passed are more than list of containers configured in config"
                                 "file: [{}]".format(container_list, configured_container_list))

            frameworkObj = frameworkUtils.getFramework(data)
            framework = frameworkObj.getName()
            common_repo = config.get('repo', '')

            repo = self.getRepository(data, common_repo, args.app_name)
            comp_dir = settingObj.getComponentsDir()
            templ_dir = settingObj.getTemplatesDir()
            secrets_dir = settingObj.getSecretsDir()

            # Create comp_dir if it doesn't exist
            if not os.path.isdir(comp_dir):
                os.makedirs(comp_dir)

            data_containers = data['containers'] if not container_list else cotainer_list
            failed_container_dict = {}

            # (vmahedia) upto this point it's all getting and checking the
            # configuration parameters

            # Required for when work_dir,component_dir,template_dir or
            # secret_env_dir is something like '.' or './temp"
            os.chdir(cur_file_path)
            app_path = self.getAppPath(appObj, args, data, repo, templ_dir)

            env = Environment(loader = FileSystemLoader("{}".format(app_path)), undefined = StrictUndefined)
            extra_vars = {}
            if 'extra_variables_path' in data:
                ev_path = self.repo_relative_path(appObj, args, repo, data['extra_variables_path'])
                with open(ev_path) as f:
                    extra_vars = yaml.load(f) if ev_path.lower().endswith('.yml') else json.load(f)

            if not hasattr(self, "identifier"):
                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(), args.app_name)

            args.app_name = self.utils.extract_app_name(args.app_name)
            hooksObj.statsd_message_list = self.statsd_message_list
            hookname = "pre_push"
            hook_input_metric = "roger-tools.rogeros_tools_exec_time," + "event=" + hookname + ",app_name=" + str(args.app_name) + ",identifier=" + str(self.identifier) + ",config_name=" + str(config_name) + ",env=" + str(environment) + ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, app_path, hook_input_metric)
            if exit_code != 0:
                raise ValueError("{} hook failed.".format(hookname))

            # ----------------------------------------------
            # (vmahedia) Figure out what the hell this loop does
            # and name it appropriately
            # it seems first part is just finding a template and Rendering
            # it against the given config, checking to see if there are errors
            # ----------------------------------------------
            # (vmahedia) Meat starts from here, probably.
            template = ''
            for container in data_containers:
                container_name = self.getContainerName(container)
                if type(container) == dict:
                    container = container[container_name]
                containerConfig = "{0}-{1}.json".format(config['name'], container_name)

                template_with_path = os.path.join(app_path, containerConfig)
                try:
                    template = env.get_template(containerConfig)
                except exceptions.TemplateNotFound as e:
                    raise ValueError("The template file {} does not exist".format(template_with_path))
                except Exception as e:
                    raise ValueError("Error while reading template from {} - {}".format(template_with_path, e))

                additional_vars = {}
                # (vmahedia)variables likes this should be at least visible within one
                # scroll up or down, move this code to near to context
                # Why are we getting the secrets everytime, this requires the file to be
                # present
                additional_vars.update(extra_vars)
                secret_vars = self.loadSecrets(secrets_dir, containerConfig, args, environment)
                if secret_vars is not None:
                    additional_vars.update(secret_vars)

                image_path = "{0}/{1}".format(roger_env['registry'], args.image_name)
                print("Rendering content from template {} for environment [{}]".format(template_with_path, environment))
                try:
                    output = self.renderTemplate(template, environment, image_path, data,
                                                 config, container, container_name, additional_vars)
                except exceptions.UndefinedError as e:
                    error_str = "The following Undefined Jinja variable error occurred. %s.\n" % e
                    print(colored(error_str, "red"), file=sys.stderr)
                    failed_container_dict[container_name] = error_str
                    # we are going to fail even if one of the container config is not valid but we will
                    # still go through the loop and collect all the errors before we bail out
                    validation_failed = True
                    pass
                # ----------------------------------------------
                # it seems the checks above can finish independent of the
                # following code, decouple this two parts, later when  the code
                # is well understood
                # ----------------------------------------------
                # Adding check to see if all jinja variables git resolved fot
                # the container
                if container_name not in failed_container_dict:
                    # Adding check so that not all apps try to mergeSecrets
                    try:
                        outputObj = json.loads(output)
                    except Exception as e:
                        raise ValueError("Error while loading json from {} - {}".format(template_with_path, e))

                    if '\"SECRET\"' in output and not args.secrets_file:
                        raise ValueError('"SECRET" string present in template, replace'
                                         'with template variables named in sercrets file')
                    output = self.mergeSecrets(output, secret_vars)
                    if output != "StandardError":
                        try:
                            comp_dir_exists = os.path.exists("{0}".format(comp_dir))
                            if not comp_dir_exists:
                                os.makedirs("{0}".format(comp_dir))
                            comp_env_dir_exists = os.path.exists("{0}/{1}".format(comp_dir, environment))
                            if not comp_env_dir_exists:
                                os.makedirs("{0}/{1}".format(comp_dir, environment))
                        except Exception as e:
                            logging.error(traceback.format_exc())
                        # (vmahedia) Should we write out the files even though there is an error with one of the
                        # containers. Although maybe users would want to see some output
                        with open("{0}/{1}/{2}".format(comp_dir, environment, containerConfig), 'wb') as fh:
                            fh.write(output)
                    else:
                        raise ValueError("Error while loading secrets to render template file variables")

            # Notify container error messages
            # let failed_container_dict just be for now, but report all the errors
            if validation_failed:
                raise Exception("Unable to render Jinja template")

            deployment_check_failed = False
            # fail if the deployment check fails

            for container in data_containers:
                container_name = self.getContainerName(container)
                containerConfig = "{0}-{1}.json".format(config['name'], container_name)
                config_file_path = "{0}/{1}/{2}".format(comp_dir, environment, containerConfig)
                result = frameworkObj.runDeploymentChecks(config_file_path, environment)
                if not result:
                    # need to give more indication about what can they do to fix this and what exactly failed
                    # in the deployment check function, we should print an error in that function as well
                    print(colored("Deployment checks failed for container - {}".format(framework, container)), "red")
                    deployment_check_failed = True

            if deployment_check_failed:
                raise Exception("Deployment Check failed for one or more containers, check logs for more info!")

            if args.skip_push:
                print(colored("Skipping push to {} framework. The rendered config file(s) are under {}/{}/".format(
                    framework, colored(comp_dir, "cyan"), colored(environment, "cyan")), "yellow"))
            else:
                # push to roger framework
                if 'owner' in config:
                    frameworkObj.act_as_user = config['owner']

                tools_version_value = self.utils.get_version()
                if self.registry not in args.image_name:
                    image_name = self.registry + "/" + args.image_name

                for container in data_containers:
                    try:
                        function_execution_start_time = datetime.now()
                        # Assume SUCCESS unless exception
                        execution_result = 'SUCCESS'
                        sc = self.utils.getStatsClient()
                    except (Exception) as e:
                        raise ValueError("{} Error : {}".format(getDebugInfo(), e))
                    try:
                        container_name = self.getContainerName(container)
                        containerConfig = "{0}-{1}.json".format(config['name'], container_name)
                        config_file_path = "{0}/{1}/{2}".format(comp_dir, environment, containerConfig)
                        # this is where actual push is happening
                        # we only push if forced, in case of failures
                        # in deployment checks
                        #
                        # (vmahedia) todo:
                        # list down scenarios in which this features
                        # will be useful
                        resp, task_id = frameworkObj.put(config_file_path, environmentObj,
                                                         container_name, environment, act_as_user)
                        # // operator does floor division, rounds up to integer
                        color = "green" if resp.status_code // 100 == 2 else "red"
                        print(colored(json.dumps(resp.json(), indent=4), color))
                        container_task_id = self.utils.modify_task_id(task_id)
                        self.task_id.extend(container_task_id)
                        if hasattr(resp, "status_code"):
                            status_code = resp.status_code
                    except (Exception) as e:
                        print("ERROR - : %s" %
                              e, file=sys.stderr)
                        execution_result = 'FAILURE'
                        raise
                    finally:
                        try:
                            if 'function_execution_start_time' not in globals() and \
                               'function_execution_start_time' not in locals():
                                function_execution_start_time = datetime.now()

                            if 'execution_result' not in globals() and \
                               'execution_result' not in locals():
                                execution_result = 'FAILURE'

                            if 'config_name' not in globals() and \
                               'config_name' not in locals():
                                config_name = ""

                            if 'environment' not in globals() and \
                               'environment' not in locals():
                                environment = "dev"

                            if 'container_name' not in globals() and \
                               'container_name' not in locals():
                                container_name = ""

                            if 'status_code' not in globals() and \
                               'status_code' not in locals():
                                status_code = "500"

                            if not hasattr(args, "app_name"):
                                args.app_name = ""

                            if 'settingObj' not in globals() and \
                               'settingObj' not in locals():
                                settingObj = Settings()

                            if 'container_task_id' not in globals() and 'container_task_id' not in locals():
                                container_task_id = []

                            if not hasattr(self, "identifier"):
                                self.identifier = self.utils.get_identifier(config_name, settingObj.getUser(),
                                                                            args.app_name)

                            if not str(status_code).startswith("20"):
                                execution_result = 'FAILURE'
                                self.outcome = 0

                            time_taken = (datetime.now() - function_execution_start_time).total_seconds()
                            for task_id in container_task_id:
                                input_metric = "roger-tools.rogeros_tools_exec_time" + \
                                               ",app_name=" + str(args.app_name) + \
                                               ",event=push" + \
                                               ",container_name=" + str(container_name) + \
                                               ",identifier=" + str(self.identifier) + \
                                               ",outcome=" + str(execution_result) + \
                                               ",response_code=" + str(status_code) + \
                                               ",config_name=" + str(config_name) + \
                                               ",env=" + str(environment) + \
                                               ",user=" + str(settingObj.getUser())
                                tup = (input_metric, time_taken)
                                self.statsd_message_list.append(tup)

                                if str(status_code).startswith("20"):
                                    metric = input_metric.replace("rogeros_tools_exec_time", "rogeros_events")
                                    metric = metric + ",source=tools" + ",task_id=" + task_id
                                    self.statsd_counter_logging(metric)

                        except (Exception) as e:
                            printException(e)
                            raise

            hooksObj.statsd_message_list = self.statsd_message_list
            hookname = "post_push"
            hook_input_metric = "roger-tools.rogeros_tools_exec_time," + "event=" + hookname + \
                                                                         ",app_name=" + str(args.app_name) + \
                                                                         ",identifier=" + str(self.identifier) + \
                                                                         ",config_name=" + str(config_name) + \
                                                                         ",env=" + str(environment) + \
                                                                         ",user=" + str(settingObj.getUser())
            exit_code = hooksObj.run_hook(hookname, data, app_path, hook_input_metric)
            if exit_code != 0:
                raise ValueError("{} hook failed.".format(hookname))
            print(colored("******Done with the PUSH step******", "green"))

        except (Exception) as e:
            raise ValueError("ERROR - {}".format(e))

if __name__ == "__main__":
    settingObj = Settings()
    appObj = AppConfig()
    frameworkUtils = FrameworkUtils()
    hooksObj = Hooks()
    roger_push = RogerPush()
    try:
        roger_push.parser = roger_push.parse_args()
        roger_push.args = roger_push.parser.parse_args()
        roger_push.main(settingObj, appObj, frameworkUtils, hooksObj, roger_push.args)
        result_list = []

        tools_version_value = roger_push.utils.get_version()
        image_name = roger_push.registry + "/" + roger_push.image_name
        image_tag_value = urllib.quote("'" + image_name + "'")

        for task_id_value in roger_push.task_id:
            statsd_message_list = roger_push.utils.append_arguments(roger_push.statsd_message_list,
                                                                    task_id=task_id_value,
                                                                    tools_version=tools_version_value,
                                                                    image_tag=image_tag_value)
            result_list.append(statsd_message_list)

        sc = roger_push.utils.getStatsClient()

        for item in roger_push.statsd_push_list:
            sc.timing(item[0], item[1])

        for lst in result_list:
            for item in lst:
                sc.timing(item[0], item[1])
    except (Exception) as e:
        printException(e)
