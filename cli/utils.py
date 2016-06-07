#!/usr/bin/python

from __future__ import print_function
import os
import sys
import statsd
from cli.settings import Settings
from cli.appconfig import AppConfig
import hashlib
import time

class Utils:

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

    def getStatsClient(self):
        settingObj = Settings()
        appObj = AppConfig()
        config_dir = settingObj.getConfigDir()
        roger_env = appObj.getRogerEnv(config_dir)
        statsd_url = ""
        statsd_port = ""
        if 'statsd_client_endpoint' in roger_env.keys():
            statsd_url = roger_env['statsd_client_endpoint']
        if 'statsd_client_port' in roger_env.keys():
            statsd_port = int(roger_env['statsd_client_port'])
        return statsd.StatsClient(statsd_url, statsd_port)

    def get_identifier(self, config_name, user_name):
        hash_value =  str(int(time.time())) + "-" + str(hashlib.sha224(config_name+"-"+user_name).hexdigest())[:8]
        return hash_value
