#!/usr/bin/python

from __future__ import print_function
import argparse
import os
import sys
from cli.settings import Settings
from cli.appconfig import AppConfig
import hashlib
import time
import json
from pkg_resources import get_distribution
# todo: use https://pypi.python.org/pypi/colorama instead of termcolor
from termcolor import colored
import inspect
import logging

# Prints filename, line number and function name we need to print in
# front of each line.
def getDebugInfo(stack_depth):
  if stack_depth < len(inspect.stack()):
      # stack_depth
      # 0 represents this line
      # 1 represents line at caller
      callerframerecord = inspect.stack()[stack_depth]
  else:
      callerframerecord = inspect.stack()[1]
  frame = callerframerecord[0]
  info = inspect.getframeinfo(frame)
  return "{}:{} fn:{}".format(info.filename, info.lineno, info.function)

def printException(e):
    logging.exception(e)
    printErrorMsg(repr(e), 3)

def printErrorMsg(error_msg, stack_depth = 2):
    print(colored("{} - {}".format(getDebugInfo(stack_depth), error_msg), "red"))

class Utils:

    def __init__(self):
        self.task_id_value = None

    def roger_version(self, root_dir):
        version = "Unknown!"
        try:
            version = get_distribution('roger_mesos_tools').version
        except Exception:
            fname = os.path.join(root_dir, "VERSION")
            if(os.path.isfile(fname)):
                with open(os.path.join(root_dir, "VERSION")) as f:
                    version = f.read().strip()
        return version

    # Expected format:
    #   moz-content-kairos-7da406eb9e8937875e0548ae1149/v0.46
    def extractFullShaAndVersion(self, image):
        if '-' not in image:
            return ''
        tokens = image.split('-')
        if len(tokens) != 0:
            return tokens[-1]
        else:
            return ''

    # Expected format:
    #   moz-content-kairos-7da406eb9e8937875e0548ae1149/v0.46
    def extractShaFromImage(self, image):
        if '/v' not in image:
            return ''
        sha = image.split('/v')
        if len(sha) != 0:
            sha = sha[0].split('-')
            if len(sha) != 0:
                return sha[-1]
        return ''

    def get_identifier(self, config_name, user_name, app_name):
        hash_value = str(int(time.time())) + "-" + str(hashlib.sha224(config_name + "-" + user_name + "-" + app_name).hexdigest())[:8]
        return hash_value

    def extract_app_name(self, value):
        if ':' in value:
            return value.split(":")[0]
        if '[' in value:
            return value.split("[")[0]
        return value

    def modify_task_id(self, task_id_list):
        modified_task_id_list = []
        try:
            for task_id in task_id_list:
                if task_id[0] == '/':
                    task_id = task_id[1:]
                task_id = task_id.replace("/", "_")
                modified_task_id_list.append(task_id)
        except (Exception) as e:
            printException(e)
        return modified_task_id_list

    def generate_task_id_list(self, data):
        task_id_list = []
        try:
            data_json = json.loads(data)
            top_level = ""
            if 'id' in data_json:
                top_level = data_json['id']
                if 'groups' in data_json:
                    for groups in data_json['groups']:
                        group_level = ""
                        if 'id' in groups:
                            group_level = groups['id']
                        if 'apps' in groups:
                            app_level = ""
                            for app in groups['apps']:
                                if type(app) == list:
                                    for item in app:
                                        if 'id' in item:
                                            app_level = item['id']
                                            task_id_list.append(str(top_level + "/" + group_level + "/" + app_level))
                                else:
                                    if 'id' in app:
                                        app_level = app['id']
                                        task_id_list.append(str(top_level + "/" + group_level + "/" + app_level))
                else:
                    task_id_list.append(str(top_level))
        except (Exception) as e:
            printException(e)
        return task_id_list

    def get_version(self):
        own_dir = os.path.dirname(os.path.realpath(__file__))
        root = os.path.abspath(os.path.join(own_dir, os.pardir))
        return self.roger_version(root)

    def repo_relative_path(self, appConfig, args, repo, path):
        '''Returns a path relative to the repo, assumed to be under [args.directory]/[repo name]'''
        repo_name = appConfig.getRepoName(repo)
        abs_path = os.path.abspath(args.directory)
        if abs_path == args.directory:
            return "{0}/{1}/{2}".format(args.directory, repo_name, path)
        else:
            return "{0}/{1}/{2}/{3}".format(os.environ.get('PWD', ''),
                                            args.directory, repo_name, path)
