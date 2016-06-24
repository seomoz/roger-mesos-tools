#!/usr/bin/python

from __future__ import print_function
import os
import sys
from cli.settings import Settings
from abc import ABCMeta, abstractmethod

settings = Settings()

class Framework(object):
    __metaclass__ = ABCMeta

    def fetchUserPass(self, env):
        if self.user is None:
            self.user = settings.getUser()
        if self.passw is None:
            self.passw = settings.getPass(env)
        print("Using u:{}, p:****".format(self.user))

    @abstractmethod
    def getName(self):
        pass

    @abstractmethod
    def get(self, roger_env, environment):
        pass

    @abstractmethod
    def put(self, file_path, environmentObj, container, environment):
        pass

    @abstractmethod
    def runDeploymentChecks(self, file_path, environment):
        pass

    @abstractmethod
    def getCurrentImageVersion(self, roger_env, environment, application):
        pass

    @abstractmethod
    def getTasks(self, roger_env, environment):
        pass
