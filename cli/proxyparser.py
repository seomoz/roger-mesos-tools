#!/usr/bin/env python

from __future__ import print_function
import os
import requests
import subprocess
import sys
import re
from cli.appconfig import AppConfig
from cli.settings import Settings
requests.packages.urllib3.disable_warnings()


class ProxyParser:

    path_begin_values = {}
    backend_services_tcp_ports = {}

    def get_proxy_config(self, environment):
        proxy_config = ""
        settingObj = Settings()
        appObj = AppConfig()
        config_dir = settingObj.getConfigDir()
        roger_env = appObj.getRogerEnv(config_dir)
        host = roger_env['environments'][environment]['host']
        proxy_config_path = roger_env['environments'][
            environment]['proxy_config_path']
        url = "{}{}".format(host, proxy_config_path)
        proxy_config = requests.get(url).json()
        return proxy_config

    def parseConfig(self, environment):
        path_begin_values = {}
        backend_tcp_ports = {}
        config = self.get_proxy_config(environment)

        for app in config['Apps']:
            if 'HTTP_PREFIX' in app['Env']:
                path_begin_values[app['Env']['HTTP_PREFIX']] = app['Id']
            if app['TcpPorts'] is not None:
                for port in app['TcpPorts'].keys():
                    backend_tcp_ports[port] = app['Id']

        self.set_path_begin_values(path_begin_values)
        self.set_backend_tcp_ports(backend_tcp_ports)

    def set_path_begin_values(self, path_begin_values_aclnames):
        self.path_begin_values = path_begin_values_aclnames

    def get_path_begin_values(self):
        return self.path_begin_values

    def set_backend_tcp_ports(self, backend_services_tcp_ports):
        self.backend_services_tcp_ports = backend_services_tcp_ports

    def get_backend_tcp_ports(self):
        return self.backend_services_tcp_ports
