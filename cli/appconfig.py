#!/usr/bin/python

from __future__ import print_function
import os
import os.path
import sys
import json
import yaml
from cli.settings import Settings


class AppConfig:

    def getRogerEnv(self, config_dir):
        roger_env = None
        env_file = '{0}/roger-mesos-toolsconfig.yml'
        with open(env_file.format(config_dir)) as roger_env_file_obj:
            roger_env = yaml.load(roger_env_file_obj) if env_file.lower(
            ).endswith('.yml') else json.load(roger_env_file_obj)
        return roger_env

    def getConfig(self, config_dir, config_file):
        config = None
        if os.path.exists(config_file):
            with open(config_file) as config_file_obj:
                config = yaml.load(config_file_obj) if config_file.lower(
                ).endswith('.yml') else json.load(config_file_obj)
        else:
            with open('{0}/{1}'.format(config_dir, config_file)) as config_file_obj:
                config = yaml.load(config_file_obj) if config_file.lower(
                ).endswith('.yml') else json.load(config_file_obj)
        return config

    def getAppData(self, config_dir, config_file, app_name):
        config = self.getConfig(config_dir, config_file)
        app_data = ''
        if app_name in config['apps']:
            app_data = config['apps'][app_name]
        return app_data

    def getRepoUrl(self, repo):
        if repo.startswith('git@github.com'):
            return repo
        else:
            settingObj = Settings()
            config_dir = settingObj.getConfigDir()
            roger_env = self.getRogerEnv(config_dir)
            if 'default_github_repo_prefix' in roger_env.keys():
                prefix = roger_env['default_github_repo_prefix']
            else:
                raise ValueError(
                    "Could not determine github repo.Please provide default \"github repo prefix\" or ensure repo startswith git@github.com")
            return str(prefix + '{}.git'.format(repo))

    def getRepoName(self, repo):
        if 'git@github' in repo:
            repo_name = repo.split("/")[1]
            repo_name = repo_name.split(".")[0]
            return str(repo_name)
        return repo
