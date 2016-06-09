#!/usr/bin/python

from __future__ import print_function
import os
import sys
import getpass


class Settings:

    def getConfigDir(self):
        config_dir = ''
        if "ROGER_CONFIG_DIR" in os.environ:
            config_dir = os.environ.get('ROGER_CONFIG_DIR')
        if config_dir.strip() == '':
            raise ValueError(
                "Environment variable $ROGER_CONFIG_DIR is not set.")
        config_dir = os.path.abspath(config_dir)
        return config_dir

    def getComponentsDir(self):
        comp_dir = ''
        if "ROGER_COMPONENTS_DIR" in os.environ:
            comp_dir = os.environ.get('ROGER_COMPONENTS_DIR')
        if comp_dir.strip() == '':
            raise ValueError(
                "Environment variable $ROGER_COMPONENTS_DIR is not set.")
        comp_dir = os.path.abspath(comp_dir)
        return comp_dir

    def getTemplatesDir(self):
        templ_dir = ''
        if "ROGER_TEMPLATES_DIR" in os.environ:
            templ_dir = os.environ.get('ROGER_TEMPLATES_DIR')
        if templ_dir.strip() == '':
            raise ValueError(
                "Environment variable $ROGER_TEMPLATES_DIR is not set.")
        return templ_dir

    def getSecretsDir(self):
        secrets_dir = ''
        if "ROGER_SECRETS_DIR" in os.environ:
            secrets_dir = os.environ.get('ROGER_SECRETS_DIR')
        if secrets_dir.strip() == '':
            raise ValueError(
                "Environment variable $ROGER_SECRETS_DIR is not set.")
        secrets_dir = os.path.abspath(secrets_dir)
        return secrets_dir

    def getCliDir(self):
        cli_dir = ''
        own_dir = os.path.dirname(os.path.realpath(__file__))
        cli_dir = os.path.abspath(os.path.join(own_dir, os.pardir))
        return cli_dir

    def getUser(self):
        user = None
        # ROGER_USER_ID env var > getpass.getuser()
        envvar = "ROGER_USER"
        if envvar in os.environ:
            user = os.environ.get(envvar)
        else:
            user = getpass.getuser()
        return user

    def getPass(self, env):
        # ROGER_USER_PASS_<ENV> > getpass.getpass()
        envvar = "ROGER_USER_PASS_{}".format(env.upper())
        if envvar in os.environ:
            return os.environ.get(envvar)
        return getpass.getpass("password for [{}] env (to avoid getting this message set the environment variable {})? ".format(env, envvar))
