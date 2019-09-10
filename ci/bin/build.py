#!/usr/bin/python

#import json
import os
import sys
import yaml
from time import sleep
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
import string
import random

def create_git_ssh_wrapper(filename="/tmp/git_ssh"):

    if os.path.exists(filename): return filename

    file_content = '''
#!/bin/bash

trap 'rm -f /tmp/.git_ssh.$$' 0

if [ "$1" = "-i" ]; then
    SSH_KEY=$2; shift; shift
    echo "GIT_TERMINAL_PROMPT=0 ssh -i $SSH_KEY -o StrictHostKeyChecking=no -oBatchMode=yes \$@" > /tmp/.git_ssh.$$
    chmod +x /tmp/.git_ssh.$$
    export GIT_SSH=/tmp/.git_ssh.$$
fi

[ "$1" = "git" ] && shift

# Run the git command
git "$@"
'''
    config_run = open(filename,'w')
    config_run.write(file_content)
    config_run.close()
    os.system("chmod 755 %s" % filename)

    return filename

def execute_return_exit(cmd):
  
    process = Popen(cmd,shell=True,bufsize=0,stdout=PIPE,stderr=STDOUT)
  
    line = process.stdout.readline()
  
    while line:
        line = line.strip()
        print line
        line = process.stdout.readline()
  
    out,error = process.communicate()
    exitcode = process.returncode
  
    return exitcode

def run_cmd(cmd,exit_error=False):

    print 'executing cmd "{}"'.format(cmd)

    exitcode = execute_return_exit(cmd)
    if exitcode == 0: return True

    if exit_error: exit(exitcode)

    return False

def run_cmds(cmds,exit_error=True):

    for cmd in cmds:
        print 'Executing "{}"'.format(cmd)
        exitcode = execute_return_exit(cmd)
        if exitcode == 0: continue
        print 'Executing "{}" failed with exitcode={}'.format(cmd,exitcode)
        if exit_error: sys.exit(1)
        return False

    return True

def execute(cmd,unbuffered=False):

    '''executes a shell command, returning status of execution,
    standard out, and standard error'''

    process = Popen(cmd,shell=True,bufsize=0,stdout=PIPE,stderr=STDOUT)

    line = process.stdout.readline()

    while line:
        line = line.strip()
        print line

    out,error = process.communicate()
    exitcode = process.returncode

    return exitcode

def id_generator(size=6,chars=string.ascii_uppercase+string.digits):

    '''generates id randomly'''

    return ''.join(random.choice(chars) for x in range(size))

def git_clone_repo():

    '''
    does a simple clone if repo doesn't exists 
    or does a pull if does exists
    '''

    repo_dir = os.environ["DOCKER_BUILD_DIR"]
    git_url = os.environ.get("REPO_URL")
    prv_key_loc = os.environ.get("REPO_KEY_LOC")
    commit = os.environ.get("COMMIT_HASH")
    branch = os.environ.get("REPO_BRANCH","master")

    if not git_url:
        print "WARN: git_url not given, not cloning %s" % (repo_dir)
        return False

    if prv_key_loc:
        wrapper_script = create_git_ssh_wrapper()
        base_cmd = "{} -i {}".format(wrapper_script,prv_key_loc)
        git_url = git_url.replace("https://github.com/","git@github.com:")
    else:
        base_cmd = None

    cmds = []

    _branch = "master"
    if not branch: _branch = branch

    add_cmd = "git pull origin {}".format(_branch)

    if base_cmd:
        cmds.append("cd {}; {} {}".format(repo_dir,base_cmd,add_cmd))
    else:
        cmds.append("cd {}; {}".format(repo_dir,add_cmd))

    if commit:
        add_cmd = "git checkout {}".format(commit)
        cmds.append("cd {}; {}".format(repo_dir,add_cmd))

    run_cmds(cmds)

    return True

def build_container():

    log_file = "/tmp/{}".format(id_generator(size=6,chars=string.ascii_uppercase+string.digits))
    repo_dir = os.environ["DOCKER_BUILD_DIR"]
    repository_uri = os.environ["REPOSITORY_URI"]
    tag = os.environ["COMMIT_HASH"][0:6]
    cmds = []
    cmd = "cd {}; docker build -t {}:{} . > {} 2>&1 ".format(repo_dir,repository_uri,tag,log_file)
    cmds.append(cmd)
    cmd = "cd {}; docker build -t {}:latest .  >> {} 2>&1".format(repo_dir,repository_uri,log_file)
    cmds.append(cmd)

    status = run_cmds(cmds,exit_error=False)

    results = {"status":status}
    results["log"] = [line.rstrip('\n') for line in open(log_file)]
    os.system("rm -rf {}".format(log_file))

    return results

def push_container():

    log_file = "/tmp/{}".format(id_generator(size=6,chars=string.ascii_uppercase+string.digits))

    repository_uri = os.environ["REPOSITORY_URI"]
    ecr_login = os.environ["ECR_LOGIN"]
    tag = os.environ["COMMIT_HASH"][0:6]
    print "Pushing latest image to repository {}, tag = {}".format(repository_uri,tag)
    cmds = []
    cmds.append(ecr_login)
    cmd = "docker push {} > {} 2>*1".format(repository_uri,log_file)
    cmds.append(cmd)

    status = run_cmds(cmds,exit_error=False)

    os.system("rm -rf {}".format(log_file))

    results = {"status":status}
    results["log"] = [line.rstrip('\n') for line in open(log_file)]
    os.system("rm -rf {}".format(log_file))

    return results

class LocalDockerCI(object):

    def __init__(self):
  
        self.build_queue_dir = os.environ.get("FASTEST_CI_QUEUE_DIR","/var/tmp/docker/fastest-ci/queue")

    def _get_next_build(self):

        filenames = sorted(os.listdir(self.build_queue_dir))
        if not filenames: return

        print filenames

        filename = os.path.join(self.build_queue_dir,filenames[0])

        return filename

    def _run(self):
        
        results = {"status":None}

        file_path = self._get_next_build()
        if not file_path: return results

        log = []

        try:
            yaml_str = open(file_path,'r').read()
            loaded_yaml = dict(yaml.load(yaml_str))
            log.append("payload from webhook loaded and read")
        except:
            loaded_yaml = None
            msg = "ERROR: could not load yaml at {} - skipping build".format(file_path)
            print msg
            log.append(msg)
            results = {"status":False}
            results["log"] = log
            return results

        os.system("rm -rf {}".format(file_path))
        if not loaded_yaml: return results

        os.environ["REPO_KEY_LOC"] = os.environ.get("REPO_KEY_LOC","/var/lib/jiffy/files/autogenerated/deploy.pem")
        os.environ["DOCKER_BUILD_DIR"] = os.environ.get("DOCKER_BUILD_DIR","/var/tmp/docker/build")
        os.environ["REPO_URL"] = loaded_yaml["repo_url"]
        os.environ["COMMIT_HASH"] = loaded_yaml["commit_hash"]
        os.environ["REPO_BRANCH"] = loaded_yaml.get("branch","master")

        try:
            status = git_clone_repo()
            log.append("clone of code with commit_hash {} succeeded".format(loaded_yaml["commit_hash"]))
        except:
            status = False

        if not status:
            msg = "ERROR: clone/pull latest code failed"
            print msg
            log.append(msg)
            results = {"status":False}
            results["log"] = log
            return results

        # REPOSITORY_URI This needs to be set for builds
        bresults = build_container()
        if not bresults.get("log"): log.extend(bresults.get("log"))
        if not bresults.get("status"):
            print "ERROR: build container failed"
            results = {"status":False}
            results["log"] = log
            return results

        presults = push_container()
        if not presults.get("log"): log.extend(presults.get("log"))
        if not presults.get("status"):
            print "ERROR: push container failed"
            results = {"status":False}
            results["log"] = log
            return results

        return results

    def run(self):

        while True:
            schedule_id = os.environ["SCHEDULE_ID"]
            results = self._run()
            if results.get("status") is False: results["status"] = "failed"
            results["schedule_id"] = schedule_id
            sleep(1)

if __name__ == "__main__":
    main = LocalDockerCI()
    main.run()

#{'status': True, 'committer': 'Gary', 'compare': 'https://github.com/bill12252016/flask_sample/compare/ed510ec66c61...feff8b8a63a5', 'event_type': 'push', 'author': 'Gary', 'url': 'https://github.com/bill12252016/flask_sample/commit/feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'branch': 'master', 'commit_hash': 'feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'repo_url': 'https://github.com/bill12252016/flask_sample', 'committed_date': '2019-09-09T17:32:05+08:00', 'message': 'testing change new string MBpz6bF6', 'authored_date': '2019-09-09T17:32:05+08:00', 'email': 'gear@thytruth.com'}