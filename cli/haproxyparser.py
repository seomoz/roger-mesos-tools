#!/usr/bin/env python

from __future__ import print_function
import os
import requests
import subprocess
import sys
import re
from cli.appconfig import AppConfig
from cli.settings import Settings


class HAProxyParser:

    path_begin_values = {}
    backend_services_tcp_ports = {}

    def get_haproxy_config(self, environment):
        haproxy_config = ""
        settingObj = Settings()
        appObj = AppConfig()
        config_dir = settingObj.getConfigDir()
        roger_env = appObj.getRogerEnv(config_dir)
        host = roger_env['environments'][environment]['host']
        haproxy_config_path = roger_env['environments'][
            environment]['haproxy_config_path']
        url = "{}{}".format(host, haproxy_config_path)
        haproxy_config = requests.get(url, stream=True)
        return haproxy_config.text

    def parseConfig(self, environment):
        path_begin_values = {}
        backend_tcp_ports = {}
        config = self.get_haproxy_config(environment)

        backend_rules_pattern = re.compile(
            "^( ).*use_backend (.*)-cluster.* if (.*)-aclrule$", re.MULTILINE)
        backend_rules = backend_rules_pattern.findall(config)
        backend_service_pattern = re.compile(
            "^listen (.*)-cluster-tcp-(.*) :(.*)", flags=re.MULTILINE)
        backends_service_names = backend_service_pattern.findall(config)
        for rule in backend_rules:
            backend_name = rule[1].replace("::", "/")
            path_begin_value = rule[2].replace("::", "/")
            path_begin_values[path_begin_value] = backend_name

        for service in backends_service_names:
            backend_service_name = service[0].replace("::", "/")
            tcp_port = service[2]
            backend_tcp_ports[tcp_port] = backend_service_name

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
