#!/usr/bin/python
from __future__ import print_function
import os
import contextlib
import sys
from datetime import datetime

from cli.webhook import WebHook
from cli.utils import Utils
from cli.utils import printException, printErrorMsg


@contextlib.contextmanager
def chdir(dirname):
    '''Withable chdir function that restores directory'''
    curdir = os.getcwd()
    try:
        os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


class Hooks:

    def __init__(self):
        self.utils = Utils()
        self.whobj = WebHook()
        self.statsd_message_list = []
        self.config_file = ""

    def run_hook(self, hookname, appdata, path):
        try:
            exit_code = 0
            execution_result = 'SUCCESS'
            self.whobj.invoke_webhook(appdata, self.config_file)
            abs_path = os.path.abspath(path)
            if "hooks" in appdata and hookname in appdata["hooks"]:
                command = appdata["hooks"][hookname]
                with chdir(abs_path):
                    print("About to run {} hook [{}] at path {}".format(
                        hookname, command, abs_path))
                    exit_code = os.system(command)
        except (Exception) as e:
            printException(e)
            execution_result = 'FAILURE'
            raise
        finally:
            # todo: maybe send a datadog event ?
            pass
        return exit_code
