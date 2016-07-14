#!/usr/bin/python

from __future__ import print_function
import os
import subprocess
import sys
import contextlib
import urllib2
import json


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

    def docker_build(self, image_tag, docker_file):
        if docker_file is not 'Dockerfile':
            exit_code = os.system(
                'docker build -f {} -t {} .'.format(docker_file, image_tag))
        else:
            exit_code = os.system('docker build -t {} .'.format(image_tag))
        if exit_code is not 0:
            raise ValueError("docker build failed")

    def docker_push(self, image):
        exit_code = os.system("docker push {0}".format(image))
        return exit_code

    def docker_search_v1(self, registry, name, application):
        result = subprocess.check_output("docker search {0}/{1}-{2}".format(
            registry, name, application), shell=True)
        return result

    def docker_search_v2(self, registry, name, application):
        url = 'http://{0}/v2/_catalog'.format(registry)
        response = urllib2.urlopen(url)
        data = json.load(response)
        result = ""
        for item in data['repositories']:
            result += item + '\n'
        return result

    def docker_search(self, registry, name, application):
        result = ""
        try:
            result = self.docker_search_v2(registry, name, application)
        except (Exception) as e:
            print("The following error occurred when attempting search using docker v2 catalog: %s" %
                  e, file=sys.stderr)
            print("Attempting docker v1 search")
            result = self.docker_search_v1(registry, name, application)
        return result
