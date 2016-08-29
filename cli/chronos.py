#!/usr/bin/python

from __future__ import print_function
import os
import sys
import requests
import json
from cli.framework import Framework
from cli.utils import Utils
utils = Utils()


class Chronos(Framework):

    def __init__(self):
        self.user = None
        self.passw = None

    def getName(self):
        return "Chronos"

    def get(self, roger_env, environment):
        self.fetchUserPass(environment)
        url = roger_env['environments'][environment][
            'chronos_endpoint'] + "/scheduler/jobs"
        resp = requests.get(url, auth=(self.user, self.passw))
        return resp.json()

    def put(self, file_path, environmentObj, container, environment, act_as_user):
        self.fetchUserPass(environment)
        data = open(file_path).read()
        chronos_resource = "scheduler/iso8601"
        if 'parents' in json.loads(data):
            chronos_resource = "scheduler/dependency"

        print("TRIGGERING CHRONOS FRAMEWORK UPDATE FOR: {}".format(container))
        print("curl -X PUT -H 'Content-type: application/json' --data-binary @{} {}/{}".format(
            file_path, environmentObj['chronos_endpoint'], chronos_resource))
        endpoint = environmentObj['chronos_endpoint']
        deploy_url = "{}/{}".format(endpoint, chronos_resource)

        if not act_as_user:
            resp = requests.put(deploy_url, data=data, headers={
                                'Content-type': 'application/json'}, auth=(self.user, self.passw))
        else:
            resp = requests.put(deploy_url, data=data, headers={
                                'Content-type': 'application/json', 'act-as-user': act_as_user}, auth=(self.user, self.passw))
        chronos_message = "{}".format(resp)
        print(chronos_message)
        task_id = []
        body = json.loads(data)
        if 'name' in body:
            task_id.append(body['name'])

        return resp, task_id

    def runDeploymentChecks(self, file_path, environment):
        print("No deployment checks for Chronos")
        return True

    def getCurrentImageVersion(self, roger_env, environment, application):
        data = self.get(roger_env, environment)
        for app in data:
            if 'name' in app:
                if application in app['name'] and 'container' in app:
                    docker_image = app['container']['image']
                    if len(docker_image.split('/v')) == 2:
                        # Image format expected
                        # moz-content-kairos-7da406eb9e8937875e0548ae1149/v0.46
                        return utils.extractFullShaAndVersion(docker_image)
                    else:
                        # Docker images of the format: grafana/grafana:2.1.3 or
                        # postgres:9.4.1
                        return docker_image

    def getTasks(self, roger_env, environment):
        print("Not yet implemented!")
