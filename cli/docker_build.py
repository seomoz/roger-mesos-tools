#!/usr/bin/python

from __future__ import print_function
import sys
import argparse
import shutil
import json
import os
import re
from copy import deepcopy
from cli.appconfig import AppConfig
from cli.dockerutils import DockerUtils

import contextlib

pattern = re.compile('.+/(\S+).git', re.IGNORECASE)


@contextlib.contextmanager
def chdir(dirname):
    '''Withable chdir function that restores directory'''
    curdir = os.getcwd()
    try:
        os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


def update_id_matches(update_id):
    if update_id is None:
        return False

    projects_update_id = None
    try:
        with open('.roger_docker_build_update_id', 'r') as f:
            projects_update_id = f.read()
    except:
        pass

    return update_id == projects_update_id


def write_update_id(update_id):
    if update_id:
        with open('.roger_docker_build_update_id', 'w') as f:
            f.write(update_id)


GIT_ACCOUNT = "seomoz"


def download_private_repos(projects, update_id=None):
    '''Clone (or pull if already existing) private projects to the "git" subdirectory.
  Takes an optional "update_id" (can be a very long string like a Gemfile) that we save
  to the subdirectory. Only pulls from the subrepos if this has changed.'''
    if not os.path.isdir('git'):
        os.mkdir('git')

    with chdir('git'):
        if update_id_matches(update_id):
            return

        for project_or_path in projects:
            matches = pattern.findall(project_or_path)
            if matches:
                project, path = matches[0], project_or_path
            else:
                project, path = project_or_path, 'git@github.com:{}/{}'.format(
                    GIT_ACCOUNT, project_or_path)

            if os.path.isdir(project):
                with chdir(project):
                    os.system('git fetch; git pull origin master')
            else:
                os.system('git clone {}'.format(path))

        write_update_id(update_id)


# SWAPAROOS
# Swaparoos swap out package.json / Gemfile etc replacing references to private Github repos with local ones
# They are language-specific and may work different ways

# Ruby / Gemfile Swaparoo

# This hack is necessary for branches to work
# It checks out the branch in the git repo while building
# It deletes the branch in case it exists so we will freshly take the
# origin/ branch, although if we only use this script, the branch never
# should exist anyway.
GEMFILE_BRANCH_HACK = '''
$gem2 = method(:gem) rescue method(:_gem)
def gem(*args)
  gem, ver, opts = args
  opts = ver  if !opts && ver.is_a?(Hash)
  if opts && opts[:git] && opts[:branch]
    if opts[:git] =~ /(git\/[^\/]+)$/
      if File.exists?($1) && opts[:branch] != 'master'
        system "cd #{$1} && (git branch -D #{opts[:branch]} || true) && git checkout -f #{opts[:branch]}"
      end
    end
  end
  $gem2[*args]
end

'''


@contextlib.contextmanager
def gemfile_swaparoo():
    '''Ruby swaparoo -- swap out Gemfile for fixed one referencing repos in local git/ directory.
    You may need to modify your Dockerfile to add the 'git' before running bundle install'''
    repo_re = re.compile('git@github.com:' + GIT_ACCOUNT +
                         '/([^\'"\\r\\n]+)\\.git')

    # Get original file
    with open('Gemfile', 'r') as f:
        orig_gemfile = f.read()
    with open('Gemfile.lock', 'r') as f:
        orig_gemfile_lock = f.read()

    projects = re.findall(repo_re, orig_gemfile)
    if projects:
            # Download private repos, but only if they haven't already been updated
            # after Gemfile / Gemfile.lock have been. We do this by storing the
            # Gemfile & Gemfile.lock in each subrepo.
        download_private_repos(projects, orig_gemfile + orig_gemfile_lock)

        # Create new Gemfile pointing to local repos
        new_gemfile = GEMFILE_BRANCH_HACK + \
            re.sub(repo_re, 'git/\\1', orig_gemfile)
        with open('Gemfile', 'w+') as f:
            f.write(new_gemfile)
        new_gemfile_lock = re.sub(repo_re, 'git/\\1', orig_gemfile_lock)
        with open('Gemfile.lock', 'w+') as f:
            f.write(new_gemfile_lock)

    # Do the docker build, then restore the original Gemfile with original
    # timestamps
    try:
        yield
    finally:
        with open('Gemfile', 'w+') as f:
            f.write(orig_gemfile)
        with open('Gemfile.lock', 'w+') as f:
            f.write(orig_gemfile_lock)


# Simply installs the modules into local node_modules; you must then not include that
# in .dockerignore. This is not ideal and I want to rewrite it
@contextlib.contextmanager
def packagejson_swaparoo():
    '''Swap out package.json for the fixed one referencing git/ repos'''
    # Get package.json
    with open('package.json', 'r') as packagejson:
        originalData = packagejson.read()
    data = json.loads(originalData)

    # Do the swaparoo
    for name, version in data['dependencies'].items():
        if('git' in version or 'https' in version or 'ssh' in version) and 'seomoz' in version:
            data['dependencies'].pop(name, None)
            print("Installing {} as a private dependency from the specified branch".format(name))
            os.system('npm install {}'.format(name))

    # Write modified
    with open('package.json', 'w+') as packagejson:
        packagejson.write(json.dumps(data, indent=2))

    try:
        yield  # do the docker build
    finally:
        # Rewrite original
        with open('package.json', 'w+') as packagejson:
            packagejson.write(originalData)


@contextlib.contextmanager
def null_swaparoo():
    '''Does nothing, a placeholder default swaparoo'''
    yield []


class Docker(object):

    def docker_build(self, dockerUtilsObj, appObj, directory, repo, projects, path, image_tag, build_args, verbose_mode, docker_file='Dockerfile', disable_swaparoo = False):
        '''run a `docker_build -t image_tag .` in the current directory, handling any private repos'''
        repo_name = appObj.getRepoName(repo)
        sourcePath = "{0}/{1}/".format(directory, repo_name)
        if os.path.isdir(sourcePath):
            os.chdir(sourcePath)

        if projects != 'none':
            download_private_repos(projects)

        os.chdir(sourcePath)
        if path != 'none':
            docker_path = sourcePath + "/{0}".format(path)
            os.chdir(docker_path)
        if disable_swaparoo:
            if os.path.isfile('package.json'):
                swaparoo = packagejson_swaparoo
            elif os.path.isfile('Gemfile'):
                swaparoo = gemfile_swaparoo
            else:
                swaparoo = null_swaparoo
            with swaparoo():
                dockerUtilsObj.docker_build(image_tag, docker_file, verbose_mode, build_args)
        else:
            dockerUtilsObj.docker_build(image_tag, docker_file, verbose_mode, build_args)

if __name__ == "__main__":
    dockerObj = Docker()
    dockerUtilsObj = DockerUtils()
    appObj = AppConfig()
    dockerObj.docker_build(dockerUtilsObj, appObj, sys.argv[1], sys.argv[2], sys.argv[
        3], sys.argv[4], sys.argv[5], sys.argv[6], 'Dockerfile')
