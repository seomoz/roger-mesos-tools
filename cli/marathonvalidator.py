#!/usr/bin/env python

from __future__ import print_function
import os
import sys
from cli.proxyparser import ProxyParser


class MarathonValidator:

    def validate(self, proxy_parser_obj, environment, path_begin_value, tcp_port_list, affinity, acl_name, message_list):
        proxy_parser_obj.parseConfig(environment)
        path_begin_check = self.check_path_begin_value(
            proxy_parser_obj, path_begin_value, affinity, acl_name, message_list)
        tcp_port_check = self.check_tcp_port(
            proxy_parser_obj, tcp_port_list, acl_name, message_list)

        return (path_begin_check and tcp_port_check)

    def check_path_begin_value(self, proxy_parser_obj, path_begin_value, affinity, acl_name, message_list):
        path_begin_values = proxy_parser_obj.get_path_begin_values()
        if path_begin_value in path_begin_values.keys():
            if path_begin_values[path_begin_value] != acl_name:
                if affinity is False:
                    message_list.append("HTTP PREFIX validation check failed. The HTTP PREFIX '{}' you are trying "
                                        "to use is already in use by app id: '{}'".format(path_begin_value, path_begin_values[path_begin_value]))
                    return False
                else:
                    message_list.append("WARNING: The HTTP PREFIX '{}' you are trying "
                                        "to use is already in use by app id: '{}'".format(path_begin_value, path_begin_values[path_begin_value]))
                    return True
            else:
                return True

        return True

    def check_tcp_port(self, proxy_parser_obj, tcp_port_list, acl_name, message_list):
        backend_services_tcp_ports = proxy_parser_obj.get_backend_tcp_ports()
        for tcp_port in tcp_port_list:
            if tcp_port in backend_services_tcp_ports.keys():
                if backend_services_tcp_ports[tcp_port] != acl_name:
                    message_list.append("TCP PORT validation check failed. The TCP PORT '{}' you are trying "
                                        "to use is already in use by app id: '{}'".format(tcp_port, backend_services_tcp_ports[tcp_port]))
                    return False

        return True
