#!/usr/bin/env python

from __future__ import print_function
import argparse
import subprocess
import json
import os
import requests
import subprocess
import sys
from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.containerconfig import ContainerConfig


def describe():
    return 'starts an interactive bash session into a task.'


class RogerShell(object):

    def parse_args(self):
        self.parser = argparse.ArgumentParser(
            prog='roger shell', description=describe())
        self.parser.add_argument('appTaskId', metavar='appTaskId',
                                 help="first few letters of application task id. Example: 'content.5684.")
        self.parser.add_argument('-e', '--env', metavar='env',
                                 help="environment to search. Example: 'dev' or 'stage'")
        self.parser.add_argument('-H', '--hostname', metavar='hostname',
                                 help="hostname to search. Example: 'daldevmesos01' or 'daldevmesos04'")
        return self.parser

    def main(self):
        self.parser = self.parse_args()
        args = self.parser.parse_args()
        config_dir = settingObj.getConfigDir()
        roger_env = appObj.getRogerEnv(config_dir)
        environment = roger_env.get('default_environment', '')

        if args.env is None:
            if "ROGER_ENV" in os.environ:
                env_var = os.environ.get('ROGER_ENV')
                if env_var.strip() == '':
                    print(
                        "Environment variable $ROGER_ENV is not set. Using the default set from roger-mesos-toolsconfig.yaml file")
                else:
                    print(
                        "Using value {} from environment variable $ROGER_ENV".format(env_var))
                    environment = env_var
        else:
            environment = args.env

        if environment not in roger_env['environments']:
            raise ValueError('Environment not found in roger-mesos-toolsconfig.yaml file.')

        hostname = ''
        containerId = ''
        if args.hostname is None:
            hostname = containerconfig.get_hostname_from_marathon(
                environment, roger_env, args.appTaskId)
        else:
            hostname = args.hostname

        if hostname != '':  # Hostname maybe empty when the given appTaskId does not match any taskId from Marathon
            (containerId, mesosTaskId) = containerconfig.get_containerid_mesostaskid(
                args.appTaskId, hostname)
        else:
            print("Most likely hostname could not be retrieved with appTaskId {0}. Hostname is also \
    an optional argument. See -h for usage.".format(args.appTaskId))

        if containerId is not '' and containerId is not None:
            print("If there are multiple containers that pattern match the given mesos task Id, \
    then will log into the first one")
            print("Executing bash in docker container - {0} on host - {1} for mesosTaskId - {2}".format(
                containerId, hostname, mesosTaskId))
            try:
                subprocess.check_call(
                    "docker -H tcp://{0}:4243 exec -it {1} bash".format(hostname, containerId), shell=True)
            except Exception as e:
                print("The following error occurred:\n (error: %s).\n" %
                      e, file=sys.stderr)
        else:
            print("No Container found on host {0} with application Task Id {1}".format(
                hostname, args.appTaskId))

if __name__ == '__main__':
    settingObj = Settings()
    appObj = AppConfig()
    containerconfig = ContainerConfig()
    roger_shell = RogerShell()
    roger_shell.main()
