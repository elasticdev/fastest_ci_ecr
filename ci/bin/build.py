#!/usr/bin/python

#import sys
import os
import json
import yaml
from time import sleep
from time import time
from edreporthelper.utilities import run_cmds
from edreporthelper.utilities import get_queue_id
from edreporthelper.utilities import git_clone_repo
from edreporthelper.utilities import execute_http_post
#from shutil import which

def build_container(dockerfile="Dockerfile"):

    repo_dir = os.environ["DOCKER_BUILD_DIR"]
    repository_uri = os.environ["REPOSITORY_URI"]
    tag = os.environ["COMMIT_HASH"][0:6]
    cmds = []
    cmds.append("cd {}; docker build -t {}:{} . -f {}".format(repo_dir,repository_uri,tag,dockerfile))
    cmds.append("cd {}; docker build -t {}:latest . -f {}".format(repo_dir,repository_uri,dockerfile))

    os.environ["TIMEOUT"] = str(os.environ.get("DOCKER_BUILD_TIMEOUT",1800))

    try:
        results = run_cmds(cmds)
    except:
        results = {"status":False}
        results["log"] = "TIMED OUT building container"

    return results

def scan_image():

    trivy_exists = None

    #if is_tool("trivy"): trivy_exists = True

    if not trivy_exists and os.path.exists("/usr/local/bin/trivy"): 
        trivy_exists = True

    if not trivy_exists:
        msg = "ERROR: Could not retrieve trivy to scan the image"
        results = {"status":False}
        results["log"] = msg
        return results

    os.environ["TIMEOUT"] = "1800"

    repository_uri = os.environ["REPOSITORY_URI"]
    tag = os.environ["COMMIT_HASH"][0:6]
    fqn_image = "{}:{}".format(repository_uri,tag)

    cmds = [ "trivy {}".format(fqn_image) ]

    try:
        results = run_cmds(cmds)
    except:
        results = {"status":False}
        results["log"] = "TIMED OUT scanning {}".format(fqn_image)

    return results

def push_container():

    repository_uri = os.environ["REPOSITORY_URI"]
    ecr_login = os.environ["ECR_LOGIN"]
    tag = os.environ["COMMIT_HASH"][0:6]
    print "Pushing image to repository {}, tag = {}".format(repository_uri,tag)
    cmds = []
    cmds.append(ecr_login)
    cmd = "docker push {}:{}".format(repository_uri,tag)
    cmds.append(cmd)

    os.environ["TIMEOUT"] = "300"

    try:
        results = run_cmds(cmds)
    except:
        results = {"status":False}
        results["log"] = "TIMED OUT pushing container to registry"

    return results

class LocalDockerCI(object):

    def __init__(self):
  
        self.build_queue_dir = os.environ.get("FASTEST_CI_QUEUE_DIR","/var/tmp/docker/fastest-ci/queue")
        self.token = os.environ["HOST_TOKEN"]
        self.queue_host = os.environ["QUEUE_HOST"]

    def clear_queue(self):

        print "clearing queue {} on init".format(self.build_queue_dir)
        return os.system("rm -rf {}/*".format(self.build_queue_dir))

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

        order["start_time"] = kwargs["start_time"]
        order["status"] = kwargs["status"]
        order["stop_time"] = str(int(time()))
        order["checkin"] = order["stop_time"]
        order["total_time"] = int(order["stop_time"]) - int(order["start_time"])
        if kwargs.get("log"): order["log"] = kwargs["log"]

        return order

    def _load_webhook(self,orders,file_path):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "loading webhook information"
        inputargs["role"] = "github/webhook_read"
        inputargs["status"] = "in_progress"

        try:
            yaml_str = open(file_path,'r').read()
            loaded_yaml = dict(yaml.load(yaml_str))
            msg = "payload from github webhook loaded and read successfully"
            inputargs["status"] = "completed"
        except:
            loaded_yaml = None
            msg = "ERROR: could not load yaml at {} - skipping build".format(file_path)
            inputargs["status"] = "failed"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        os.system("rm -rf {}".format(file_path))
        orders.append(self._get_order(**inputargs))

        return inputargs,loaded_yaml

    def _clone_code(self,orders,loaded_yaml):

        event_type = loaded_yaml.get("event_type")
        dest_branch = loaded_yaml.get("dest_branch")
        src_branch = loaded_yaml.get("src_branch")
        branch = loaded_yaml.get("branch")
        if not branch: branch = "master"

        os.environ["REPO_KEY_LOC"] = os.environ.get("REPO_KEY_LOC","/var/lib/jiffy/files/autogenerated/deploy.pem")
        os.environ["DOCKER_BUILD_DIR"] = os.environ.get("DOCKER_BUILD_DIR","/var/tmp/docker/build")
        os.environ["REPO_URL"] = loaded_yaml["repo_url"]
        os.environ["COMMIT_HASH"] = loaded_yaml["commit_hash"]

        # if push, then we should use branch
        os.environ["REPO_BRANCH"] = branch

        # if pull request, then we should use src branch that 
        # is being pulled in
        if event_type == "pull_request" and src_branch:
            os.environ["REPO_BRANCH"] = src_branch

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "git pull of {} commit {}".format(loaded_yaml["repo_url"],loaded_yaml["commit_hash"])
        inputargs["role"] = "git/clone_code"
        inputargs["status"] = "in_progress"

        results = git_clone_repo()

        if results.get("log"): 
            inputargs["log"] = results["log"]

        if results.get("status") is False: 
            msg = "ERROR: cloning code failed"
            inputargs["status"] = "failed"
        else:
            msg = "cloning code succeeded"
            inputargs["status"] = "completed"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        orders.append(self._get_order(**inputargs))

        return inputargs

    def _test_code(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "test of coding with {}".format(os.environ["DOCKER_FILE_TEST"])
        inputargs["role"] = "docker/unit_test"
        inputargs["status"] = "in_progress"
        # REPOSITORY_URI This needs to be set for builds
        results = build_container(os.environ["DOCKER_FILE_TEST"])
        if results.get("log"): inputargs["log"] = results["log"]

        if results.get("status") is False: 
            msg = "ERROR: testing of code failed"
            inputargs["status"] = "failed"
        else:
            msg = "testing of code succeeded"
            inputargs["status"] = "completed"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        orders.append(self._get_order(**inputargs))

        return inputargs

    def _build_container(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "building of container with {}".format(os.environ["DOCKER_FILE"])
        inputargs["role"] = "docker/build"
        inputargs["status"] = "in_progress"

        # REPOSITORY_URI This needs to be set for builds
        dockerfile = os.environ.get("DOCKER_FILE")
        if not dockerfile: dockerfile = "Dockerfile"
        results = build_container(dockerfile)
        if results.get("log"): inputargs["log"] = results["log"]

        if not results.get("status"):
            inputargs["status"] = "failed"
            msg = "building of container failed"
        else:
            inputargs["status"] = "completed"
            msg = "building of container succeeded"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        orders.append(self._get_order(**inputargs))

        return inputargs

    def _push_container(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "pushing of container"
        inputargs["role"] = "docker/push"
        inputargs["status"] = "in_progress"

        results = push_container()
        if results.get("log"): inputargs["log"] = results["log"]

        if not results.get("status"):
            msg = "pushing of container failed"
            inputargs["status"] = "failed"
        else:
            msg = "pushing of container succeeded"
            inputargs["status"] = "completed"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        orders.append(self._get_order(**inputargs))

        return inputargs

    def _scan_image(self,orders):

        inputargs = {"start_time":str(int(time()))}
        inputargs["human_description"] = "scanning of image"
        inputargs["role"] = "security/scan"
        inputargs["status"] = "in_progress"

        results = scan_image()
        if results.get("log"): inputargs["log"] = results["log"]

        if not results.get("status"):
            msg = "scanning of image failed"
            inputargs["status"] = "failed"
        else:
            msg = "scanning of image succeeded"
            inputargs["status"] = "completed"

        if not inputargs.get("log"): inputargs["log"] = msg
        print inputargs.get("log")

        orders.append(self._get_order(**inputargs))

        return inputargs

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

        if not orders: return data

        # place other fields orders

        wt = 1
        
        for order in orders:
            if os.environ.get("PROJECT_ID"): order["project_id"] = os.environ["PROJECT_ID"]
            if os.environ.get("SCHEDULE_ID"): order["schedule_id"] = os.environ["SCHEDULE_ID"]
            if os.environ.get("SCHED_TYPE"): order["sched_type"] = os.environ["SCHED_TYPE"]
            if os.environ.get("SCHED_NAME"): order["sched_name"] = os.environ["SCHED_NAME"]
            if os.environ.get("JOB_NAME"): order["job_name"] = os.environ["JOB_NAME"]
            if os.environ.get("JOB_INSTANCE_ID"): order["job_instance_id"] = os.environ["JOB_INSTANCE_ID"]

            order["automation_phase"] = "continuous_delivery"
            order["wt"] = wt
            wt += 1

        data["orders"] = orders

        return data

    def _run(self):

        file_path = self._get_next_build()
        if not file_path: return None,None,None

        # Get new orders
        orders = []

        # load webhook
        wresults,loaded_yaml = self._load_webhook(orders,file_path)
        if wresults.get("status") == "failed": return wresults["status"],orders,loaded_yaml

        # clone code
        cresults = self._clone_code(orders,loaded_yaml)
        if cresults.get("status") == "failed": return cresults.get("status"),orders,loaded_yaml

        # test code if necessary
        if os.environ.get("DOCKER_FILE_TEST") and os.path.exists("{}/{}".format(os.environ["DOCKER_BUILD_DIR"],os.environ["DOCKER_FILE_TEST"])):
            print 'executing Docker test with {}'.format(os.environ["DOCKER_FILE_TEST"])
            tresults = self._test_code(orders)
            if tresults.get("status") == "failed": return tresults.get("status"),orders,loaded_yaml

        # build code
        bresults = self._build_container(orders)
        if bresults.get("status") == "failed": return bresults.get("status"),orders,loaded_yaml

        # push container
        presults = self._push_container(orders)
        if presults.get("status") == "failed": return presults.get("status"),orders,loaded_yaml

        # scan image
        enable_scan_file = "{}/{}/{}".format(os.environ["DOCKER_BUILD_DIR"],"elasticdev","security_scan")
        if os.path.exists(enable_scan_file):
            sresults = self._scan_image(orders)
            if sresults.get("status") == "failed": return sresults.get("status"),orders,loaded_yaml

        return "successful",orders,loaded_yaml

    def run(self):

        while True:

            # Get new data
            data = self._get_new_data()

            status,orders,loaded_yaml = self._run()

            if status is None: 
                #print "Not new yml files to load"
                sleep(1)
                continue

            print "The webhook info has been loaded and processed. \n{}".format(loaded_yaml)

            data["commit"] = loaded_yaml

            publish_vars = loaded_yaml.copy()
            if "status" in publish_vars: del publish_vars["status"]

            repository_uri = os.environ["REPOSITORY_URI"]
            tag = loaded_yaml["commit_hash"][0:6]
            publish_vars["docker_image"] = "{}:{}".format(repository_uri,tag)
            publish_vars["repository_uri"] = os.environ["REPOSITORY_URI"]
            data["publish_vars"] = publish_vars

            data = self._close_pipeline(status,data,orders)

            api_endpoint = "https://{}/{}".format(self.queue_host,"api/v1.0/run")
            inputargs = {"verify":False}
            inputargs["headers"] = {'content-type': 'application/json'}
            inputargs["headers"]["Token"] = self.token
            inputargs["api_endpoint"] = api_endpoint
            inputargs["data"] = json.dumps(data)

            #print "sending results \n{} to \n\n{}\n\n".format(data,api_endpoint)
            print "sending results to {}".format(api_endpoint)

            execute_http_post(**inputargs)
            sleep(1)

if __name__ == "__main__":
    main = LocalDockerCI()
    main.clear_queue()
    main.run()
