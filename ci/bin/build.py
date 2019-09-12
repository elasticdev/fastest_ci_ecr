#!/usr/bin/python

import os
import sys
import json
import datetime
import yaml
from time import sleep
from time import time
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
import string
import random
import requests

class DateTimeJsonEncoder(json.JSONEncoder):

    def default(self,obj):

        if isinstance(obj,datetime.datetime):
            #newobject = str(obj.timetuple())
            newobject = '-'.join([ str(element) for element in list(obj.timetuple())][0:6])
            return newobject

        return json.JSONEncoder.default(self,obj)

def print_json(results):
    print json.dumps(results,sort_keys=True,cls=DateTimeJsonEncoder,indent=4)

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

    _logs = []

    for cmd in cmds:
        result = run_cmd(cmd)
        if result.get("logs"): _logs.extend(result["logs"])
        if result.get("status") is True: continue
        status = False
        break

    logs = '\n'.join(_logs)

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

def execute_http_post(**kwargs):

    headers = kwargs["headers"]
    api_endpoint = kwargs["api_endpoint"]
    data = kwargs.get("data")
    verify = kwargs.get("verify")

    inputargs = {"headers":headers}
    inputargs["timeout"] = 900

    if verify:
        inputargs["verify"] = True
    else:
        inputargs["verify"] = False

    if data: inputargs["data"] = data

    req = requests.post(api_endpoint,**inputargs)

    status_code = int(req.status_code)

    #status code between 400 and 500 are failures.
    if status_code > 399 and status_code < 600: 
        print "ERROR: Looks like the http post failed!"
        print ''
        print req
        print ''
        print ''
        return False

    print "ERROR: Looks like the http post succeeded!"

    return True

def get_queue_id(size=6,input_string=None):

    date_epoch =str(int(time()))
    queue_id = "{}{}".format(date_epoch,id_generator(size))

    return queue_id

class LocalDockerCI(object):

    def __init__(self):
  
        self.build_queue_dir = os.environ.get("FASTEST_CI_QUEUE_DIR","/var/tmp/docker/fastest-ci/queue")
        self.token = os.environ["HOST_TOKEN"]
        self.queue_host = os.environ["QUEUE_HOST"]

    def _get_next_build(self):

        filenames = sorted(os.listdir(self.build_queue_dir))
        if not filenames: return

        print 'Queue contains {}'.format(filenames)

        filename = os.path.join(self.build_queue_dir,filenames[0])

        print 'Returning {} to build'.format(filename)

        return filename

    def _get_order(self,**kwargs):

        order = {"queue_id":get_queue_id(size=15)}
        order["human_description"] = kwargs["human_description"]
        order["role"] = kwargs["role"]

        order["log"] = kwargs["log"]
        order["start_time"] = kwargs["start_time"]
        order["status"] = kwargs["status"]
        order["stop_time"] = str(int(time()))
        order["checkin"] = order["stop_time"]
        order["total_time"] = int(order["stop_time"]) - int(order["start_time"])

        return order

    def _load_webhook(self,orders,file_path):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "loading webhook information"
        inputargs["role"] = "github/webhook_read"
        inputargs["status"] = "in_progress"

        try:
            yaml_str = open(file_path,'r').read()
            loaded_yaml = dict(yaml.load(yaml_str))
            inputargs["log"] = "payload from webhook loaded and read"
            inputargs["status"] = "completed"
        except:
            loaded_yaml = None
            msg = "ERROR: could not load yaml at {} - skipping build".format(file_path)
            print msg
            inputargs["log"] = msg
            inputargs["status"] = "failed"

        os.system("rm -rf {}".format(file_path))
        orders.append(self._get_order(**inputargs))

        return inputargs["status"],loaded_yaml

    def _clone_code(self,orders,loaded_yaml):

        os.environ["REPO_KEY_LOC"] = os.environ.get("REPO_KEY_LOC","/var/lib/jiffy/files/autogenerated/deploy.pem")
        os.environ["DOCKER_BUILD_DIR"] = os.environ.get("DOCKER_BUILD_DIR","/var/tmp/docker/build")
        os.environ["REPO_URL"] = loaded_yaml["repo_url"]
        os.environ["COMMIT_HASH"] = loaded_yaml["commit_hash"]
        os.environ["REPO_BRANCH"] = loaded_yaml.get("branch","master")

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "git pull of {} commit {}".format(loaded_yaml["repo_url"],loaded_yaml["commit_hash"])
        inputargs["role"] = "git/clone_code"
        inputargs["status"] = "in_progress"

        results = git_clone_repo()
        if results.get("logs"): inputargs["log"] = results["logs"]

        if results.get("status") is False: 
            print "ERROR: cloning code failed"
            inputargs["status"] = "failed"
        else:
            inputargs["status"] = "completed"

        orders.append(self._get_order(**inputargs))

        return inputargs["status"]

    def _test_code(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "test of coding with {}".format(os.environ["DOCKER_FILE_TEST"])
        inputargs["role"] = "docker/unit_test"
        inputargs["status"] = "in_progress"
        # REPOSITORY_URI This needs to be set for builds
        results = build_container(os.environ["DOCKER_FILE_TEST"])
        if results.get("logs"): inputargs["log"] = results["logs"]

        if results.get("status") is False: 
            print "ERROR: testing of code failed"
            inputargs["status"] = "failed"
        else:
            inputargs["status"] = "completed"

        orders.append(self._get_order(**inputargs))

        return inputargs["status"]

    def _build_container(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "building of container with {}".format(os.environ["DOCKER_FILE"])
        inputargs["role"] = "docker/build"
        inputargs["status"] = "in_progress"

        # REPOSITORY_URI This needs to be set for builds
        dockerfile = os.environ.get("DOCKER_FILE")
        if not dockerfile: dockerfile = "Dockerfile"
        results = build_container(dockerfile)
        if results.get("logs"): inputargs["log"] = results["logs"]

        if not results.get("status"):
            print "ERROR: build container failed"
            inputargs["status"] = "failed"
        else:
            inputargs["status"] = "completed"

        orders.append(self._get_order(**inputargs))

        return inputargs["status"]

    def _push_container(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "pushing of container"
        inputargs["role"] = "docker/push"
        inputargs["status"] = "in_progress"

        results = push_container()
        if results.get("logs"): inputargs["log"] = results["logs"]

        if not results.get("status"):
            print "ERROR: push container failed"
            inputargs["status"] = "failed"
        else:
            inputargs["status"] = "completed"

        orders.append(self._get_order(**inputargs))

        return inputargs["status"]

    def _get_new_data(self):

        values = {"status":"running"}
        values["start_time"] = str(int(time()))
        values["automation_phase"] = "continuous_delivery"
        values["orders"] = []
        values["job_name"] = "docker_ci"
        values["run_title"] = "docker_ci"
        values["sched_name"] = "docker_ci"
        values["sched_type"] = "build"

        if os.environ.get("PROJECT_ID"): values["project_id"] = os.environ["PROJECT_ID"]
        if os.environ.get("SCHEDULE_ID"): values["schedule_id"] = os.environ["SCHEDULE_ID"]
        if os.environ.get("SCHED_TYPE"): values["sched_type"] = os.environ["SCHED_TYPE"]
        if os.environ.get("SCHED_NAME"): values["sched_name"] = os.environ["SCHED_NAME"]
        if os.environ.get("JOB_NAME"): values["job_name"] = os.environ["JOB_NAME"]
        if os.environ.get("RUN_TITLE"): values["run_title"] = os.environ["RUN_TITLE"]

        values["first_jobs"] = [ values["job_name"] ]
        values["final_jobs"] = [ values["job_name"] ]

        return values

    def _close_pipeline(self,status,data,orders=None):

        data["status"] = status
        data["stop_time"] = str(int(time()))
        data["total_time"] = int(data["stop_time"]) - int(data["start_time"])
        if orders: data["orders"] = orders

        return data

    def _run(self):

        file_path = self._get_next_build()
        if not file_path: return None,None,None

        # Get new orders
        orders = []

        # load webhook
        status,loaded_yaml = self._load_webhook(orders,file_path)
        if status == "failed": return status,orders,loaded_yaml

        # clone code
        status = self._clone_code(orders,loaded_yaml)
        if status == "failed": return status,orders,loaded_yaml

        # test code if necessary
        if os.environ.get("DOCKER_FILE_TEST"):
            status = self._test_code(orders)
            if status == "failed": return status,orders,loaded_yaml

        # build code
        status = self._build_container(orders)
        if status == "failed": return status,orders,loaded_yaml

        ## Testingyoyo
        ## push container
        #status = self._push_container(orders)
        #if status == "failed": return status,orders,loaded_yaml

        return "successful",orders,loaded_yaml

    def run(self):

        while True:

            status,orders,loaded_yaml = self._run()

            if status is None: 
                sleep(1)
                continue

            #try:
            #    status,orders = self._run()
            #    if status is None: raise
            #except:
            #    print "ERROR: Something went wrong with testing and building the code"
            #    sleep(1)
            #    continue

            # Get new data
            data = self._get_new_data()
            data["commit"] = loaded_yaml
            publish_vars = loaded_yaml.copy()

            for key,var in publish_vars.iteritems(): 
                if not var: del publish_vars[key]

            data["publish_vars"] = publish_vars
            data = self._close_pipeline(status,data,orders)

            inputargs = {"verify":False}
            inputargs["headers"] = {'content-type': 'application/json'}
            inputargs["headers"]["Token"] = self.token
            inputargs["api_endpoint"] = "https://{}/{}".format(self.queue_host,"api/v1.0/run")
            inputargs["data"] = json.dumps(data)
            execute_http_post(**inputargs)
            sleep(1)

if __name__ == "__main__":
    main = LocalDockerCI()
    main.run()

#{'status': True, 'committer': 'Gary', 'compare': 'https://github.com/bill12252016/flask_sample/compare/ed510ec66c61...feff8b8a63a5', 'event_type': 'push', 'author': 'Gary', 'url': 'https://github.com/bill12252016/flask_sample/commit/feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'branch': 'master', 'commit_hash': 'feff8b8a63a5bb86f9c1ddeea259b33fd4bcb0e6', 'repo_url': 'https://github.com/bill12252016/flask_sample', 'committed_date': '2019-09-09T17:32:05+08:00', 'message': 'testing change new string MBpz6bF6', 'authored_date': '2019-09-09T17:32:05+08:00', 'email': 'gear@thytruth.com'}
