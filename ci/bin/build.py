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

def execute_cmd(cmd):
  
    process = Popen(cmd,shell=True,bufsize=0,stdout=PIPE,stderr=STDOUT)
  
    line = process.stdout.readline()
  
    while line:
        line = line.strip()
        print line
        line = process.stdout.readline()
  
    out,error = process.communicate()
    exitcode = process.returncode
  
    return exitcode

def run_cmd(cmd):

    log_file = "/tmp/{}".format(id_generator(size=6,chars=string.ascii_uppercase+string.digits))

    print 'executing cmd "{}"'.format(cmd)

    exitcode = execute_cmd("{} > {} 2>&1".format(cmd,log_file))

    if exitcode == 0: 
        results = {"status":True}
    else:
        results = {"status":False}

    results["logs"] = [line.rstrip('\n') for line in open(log_file,"r")]

    os.system("rm -rf {}".format(log_file))

    return results

def run_cmds(cmds):

    status = True

    logs = []

    for cmd in cmds:
        result = run_cmd(cmd)
        if result.get("logs"): logs.extend(result["logs"])
        if result.get("status") is True: continue
        status = False
        break

    results = {"status":status}
    results["logs"] = logs

    return results

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
        msg = "WARN: git_url not given, not cloning %s" % (repo_dir)
        results = {"logs":msg,"status":False}
        return results

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

    return run_cmds(cmds)

def build_container(dockerfile="Dockerfile"):

    repo_dir = os.environ["DOCKER_BUILD_DIR"]
    repository_uri = os.environ["REPOSITORY_URI"]
    tag = os.environ["COMMIT_HASH"][0:6]
    cmds = []
    cmds.append("cd {}; docker build -t {}:{} . -f {}".format(repo_dir,repository_uri,tag,dockerfile))
    cmds.append("cd {}; docker build -t {}:latest . -f {}".format(repo_dir,repository_uri,dockerfile))

    return run_cmds(cmds)

def push_container():

    repository_uri = os.environ["REPOSITORY_URI"]
    ecr_login = os.environ["ECR_LOGIN"]
    tag = os.environ["COMMIT_HASH"][0:6]
    print "Pushing latest image to repository {}, tag = {}".format(repository_uri,tag)
    cmds = []
    cmds.append(ecr_login)
    cmd = "docker push {}".format(repository_uri)
    cmds.append(cmd)

    return run_cmds(cmds)

class LocalDockerCI(object):

    def __init__(self):
  
        self.build_queue_dir = os.environ.get("FASTEST_CI_QUEUE_DIR","/var/tmp/docker/fastest-ci/queue")

    def _get_next_build(self):

        filenames = sorted(os.listdir(self.build_queue_dir))
        if not filenames: return

        print 'Queue contains {}'.format(filenames)

        filename = os.path.join(self.build_queue_dir,filenames[0])

        print 'Returning {} to build'.format(filename)

        return filename

    def _run(self):
        
        results = {"status":None}

        file_path = self._get_next_build()
        if not file_path: return results

        logs = []

        try:
            yaml_str = open(file_path,'r').read()
            loaded_yaml = dict(yaml.load(yaml_str))
            logs.append("payload from webhook loaded and read")
        except:
            loaded_yaml = None
            msg = "ERROR: could not load yaml at {} - skipping build".format(file_path)
            print msg
            logs.append(msg)
            results = {"status":False}
            results["logs"] = logs
            return results

        os.system("rm -rf {}".format(file_path))
        if not loaded_yaml: return results

        os.environ["REPO_KEY_LOC"] = os.environ.get("REPO_KEY_LOC","/var/lib/jiffy/files/autogenerated/deploy.pem")
        os.environ["DOCKER_BUILD_DIR"] = os.environ.get("DOCKER_BUILD_DIR","/var/tmp/docker/build")
        os.environ["REPO_URL"] = loaded_yaml["repo_url"]
        os.environ["COMMIT_HASH"] = loaded_yaml["commit_hash"]
        os.environ["REPO_BRANCH"] = loaded_yaml.get("branch","master")

        status = True

        cresults = git_clone_repo()
        if cresults.get("logs"): logs.extend(cresults["logs"])
        if not cresults.get("status"):
            print "ERROR: cloning code failed"
            results = {"status":False}
            results["logs"] = logs
            return results

        if not status:
            msg = "ERROR: clone/pull latest code failed"
            print msg
            logs.append(msg)
            results = {"status":False}
            results["logs"] = logs
            return results

        if os.environ.get("DOCKER_FILE_TEST"):
            # REPOSITORY_URI This needs to be set for builds
            bresults = build_container(os.environ["DOCKER_FILE_TEST"])
            if bresults.get("logs"): logs.extend(bresults["logs"])
            if not bresults.get("status"):
                print "ERROR: testing of code failed"
                results = {"status":False}
                results["logs"] = logs
                return results

        # REPOSITORY_URI This needs to be set for builds
        dockerfile = os.environ.get("DOCKER_FILE")
        if not dockerfile: dockerfile = "Dockerfile"
        bresults = build_container(dockerfile)
        if bresults.get("logs"): logs.extend(bresults["logs"])
        if not bresults.get("status"):
            print "ERROR: build container failed"
            results = {"status":False}
            results["logs"] = logs
            return results

        msg = "build container succeeded"
        logs.append(msg)

        presults = push_container()
        if presults.get("logs"): logs.extend(presults.get("logs"))
        if not presults.get("status"):
            print "ERROR: push container failed"
            results = {"status":False}
            results["logs"] = logs
            return results

        msg = "push container succeeded"
        logs.append(msg)

        results["logs"] = logs
        return results

    def run(self):

        while True:

            schedule_id = os.environ["SCHEDULE_ID"]
            
            try:
                results = self._run()
            except:
                print "ERROR: Something went wrong with testing and building the code"
                continue

            if results.get("status") is False: results["status"] = "failed"
            results["schedule_id"] = schedule_id

            if results.get("logs"):
                print '*'*32
                print '*'*32
                print 'Log for test and build'
                print ''
                for log in results["logs"]:
                    print log
                print ''
                print '*'*32
                print '*'*32

            sleep(1)

if __name__ == "__main__":
    main = LocalDockerCI()
    main.run()

#{'status': True, 'committer': 'Gary', 'compare': 'https://github.com/bill12252016/flask_sample/compare/ed510ec66c61...feff8b8a63a5', 'event_type': 'push', 'author': 'Gary', 'url': 'https://github.com/bill12252016/flask_sample/commit/feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'branch': 'master', 'commit_hash': 'feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'repo_url': 'https://github.com/bill12252016/flask_sample', 'committed_date': '2019-09-09T17:32:05+08:00', 'message': 'testing change new string MBpz6bF6', 'authored_date': '2019-09-09T17:32:05+08:00', 'email': 'gear@thytruth.com'}
