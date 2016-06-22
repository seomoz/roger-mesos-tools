#!/usr/bin/env python

from __future__ import print_function
import argparse
import subprocess
import json
import os
import requests
import subprocess
import sys
from tabulate import tabulate
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.marathon import Marathon
from cli.haproxyparser import HAProxyParser


def describe():
    return "displays information about the currently active applications and tasks."


class RogerPS(object):

    def parse_args(self):
        parser = argparse.ArgumentParser(
            prog='roger ps', description=describe())
        parser.add_argument('-e', '--env', metavar='env',
                            help="environment to search. Example: 'dev' or 'stage'")
        parser.add_argument(
            '-v', '--verbose', help="show extended information for each task", action="store_true")
        return parser

    def get_app_details(self, framework, haproxyparser, environment, args, roger_env):
        app_details = {}
        instances = {}
        instance_details = self.get_instance_details(
            framework, roger_env, environment)
        app_envs = self.get_app_envs(framework, roger_env, environment)
        for task_id in instance_details:
            app_id = instance_details[task_id][0]
            if app_id in instances.keys():
                tasks_list = instances[app_id]
                tasks_list.append(task_id)
                instances[app_id] = tasks_list
            else:
                tasks_list = []
                tasks_list.append(task_id)
                instances[app_id] = tasks_list

        haproxyparser.parseConfig(environment)
        http_prefixes = haproxyparser.get_path_begin_values()
        tcp_ports = haproxyparser.get_backend_tcp_ports()

        app_ids = {}
        for app_id in instances.keys():
            http_prefix = ""
            http_url = "-"
            tcp_port_list = []
            num_instances = len(instances[app_id])
            for k, v in http_prefixes.iteritems():
                if app_id == v:
                    http_prefix = k
                    if app_id in app_envs.keys():
                        if 'HTTP_PORT' in app_envs[app_id]:
                            http_url = "{}{}".format(roger_env['environments'][
                                                     environment]['host'], http_prefix)
                            break
            for k, v in tcp_ports.iteritems():
                if app_id == v:
                    tcp_port_list.append(k)
            app_details = {}
            app_details["instances"] = num_instances
            app_details["http_url"] = http_url
            if len(tcp_port_list) != 0:
                app_details["tcp_port_list"] = ", ".join(tcp_port_list)
            else:
                app_details["tcp_port_list"] = "-"
            if args.verbose:
                task_ids = {}
                for task_id in instances[app_id]:
                    task_details = {}
                    task_details["hostname"] = instance_details[task_id][1]
                    task_details["ports"] = instance_details[task_id][2]
                    task_details["started_at"] = instance_details[task_id][3]
                    task_ids[task_id] = task_details
                app_details["tasks"] = task_ids
            app_ids[app_id] = app_details

        app_details["apps"] = app_ids
        return app_details

    def print_app_details(self, app_details, args):
        apps = []
        for app_id in app_details["apps"].keys():
            app = []
            app_data = app_details["apps"][app_id]
            app.append("{} ({} instances)".format(app_id, app_data[
                       "instances"])) if args.verbose else app.append(app_id)
            app.append(app_data["instances"]) if not args.verbose else None
            app.append(app_data["http_url"])
            app.append(app_data["tcp_port_list"])
            apps.append(app)
            if args.verbose:
                tasks = []
                for task_id in app_data["tasks"]:
                    task_data = app_data["tasks"][task_id]
                    app = []
                    app.append("|--{}".format(task_id))
                    app.append("{}:{}".format(
                        task_data["hostname"], task_data["ports"]))
                    app.append(task_data["started_at"])
                    apps.append(app)
                apps.append(["", "", ""])

        if args.verbose:
            headers = [
                "App Id (Task Id)", "Http Url (Host:[Ports])", "TCP Ports (Started At)"]
        else:
            headers = ["App Id", "Instances", "Http Url", "TCP Ports"]
        print("{}".format(tabulate(apps, headers=headers, tablefmt="simple")))

    def get_app_envs(self, framework, roger_env, environment):
        app_envs = framework.getAppEnvDetails(roger_env, environment)
        return app_envs

    def get_instance_details(self, framework, roger_env, environment):
        instance_details = framework.getInstanceDetails(roger_env, environment)
        return instance_details

    def main(self, settings, appconfig, framework, haproxyparser, args):
        config_dir = settings.getConfigDir()
        roger_env = appconfig.getRogerEnv(config_dir)
        environment = roger_env.get('default_environment', '')

        if args.env is None:
            if "ROGER_ENV" in os.environ:
                env_var = os.environ.get('ROGER_ENV')
                if env_var.strip() == '':
                    print(
                        "Environment variable $ROGER_ENV is not set.Using the default set from roger-mesos-toolsconfig.yaml file")
                else:
                    print(
                        "Using value {} from environment variable $ROGER_ENV".format(env_var))
                    environment = env_var
        else:
            environment = args.env

        if environment not in roger_env['environments']:
            raise ValueError('Environment not found in roger-mesos-toolsconfig.yaml file.')

        app_details = self.get_app_details(
            framework, haproxyparser, environment, args, roger_env)
        self.print_app_details(app_details, args)


if __name__ == '__main__':
    settings = Settings()
    appconfig = AppConfig()
    framework = Marathon()
    haproxyparser = HAProxyParser()
    roger_ps = RogerPS()
    roger_ps.parser = roger_ps.parse_args()
    roger_ps.args = roger_ps.parser.parse_args()
    roger_ps.main(settings, appconfig, framework, haproxyparser, roger_ps.args)
