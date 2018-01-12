#!/usr/bin/python

from __future__ import print_function
import os
import subprocess
import sys
import contextlib
import requests
import json
from cli.utils import printException, printErrorMsg
from termcolor import colored
requests.packages.urllib3.disable_warnings()


@contextlib.contextmanager
def chdir(dirname):
    '''Withable chdir function that restores directory'''
    curdir = os.getcwd()
    try:
        os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


class DockerUtils:

    def docker_build(self, image_tag, docker_file, verbose_mode, build_args):
        build_arg_str = ""
        if build_args:
            for key, value in build_args.iteritems():
                build_arg_str = build_arg_str + "--build-arg {}={} ".format(key, value)

        redirect = " >/dev/null 2>&1"
        if verbose_mode:
            redirect = ""
        if docker_file is not 'Dockerfile':
            exit_code = os.system(
                'docker build -f {} -t {} {} . {}'.format(docker_file, image_tag, build_arg_str, redirect))
        else:
            exit_code = os.system('docker build -t {} {} . {}'.format(image_tag, build_arg_str, redirect))
        if exit_code is not 0:
            raise ValueError("docker build failed")

    def docker_push(self, image, verbose_mode):
        redirect = " >/dev/null 2>&1"
        if verbose_mode:
            redirect = ""
        exit_code = os.system("docker push {} {}".format(image, redirect))
        return exit_code

    def docker_search_v1(self, registry, name, application):
        result = subprocess.check_output("docker search {0}/{1}-{2}".format(
            registry, name, application), shell=True)
        return result

    def docker_search_v2(self, registry):
        url = 'http://{}/v2/_catalog?n=10000'.format(registry)
        response = requests.get(url)
        data = response.json()
        tmp_repos_list = data['repositories']
        result = ""
        while(tmp_repos_list):
            for item in tmp_repos_list:
                result += item + '\n'
            last_fetched_repo = tmp_repos_list[-1]
            url = 'http://{}/v2/_catalog?n=10000&last={}'.format(registry, last_fetched_repo)
            response = requests.get(url)
            data = response.json()
            tmp_repos_list = data['repositories']

        return result

    def docker_search(self, registry, name, application):
        result = ""
        try:
            result = self.docker_search_v2(registry)
        except (Exception) as e:
            error_message = "Error when attempting search using docker v2 catalog: {} ".format(e)
            printException(error_message)
            print(colored("Attempting docker v1 search", "yellow"))
            result = self.docker_search_v1(registry, name, application)
        return result
