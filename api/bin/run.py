#!/usr/bin/python

import os
import yaml
import json
import requests
import ipaddress
from hashlib import sha1
from sys import hexversion
from time import time
#from copy import deepcopy

import hmac
import six

from flask import request
from flask import Flask

from flask_restful import Resource
from flask_restful import Api

#app = Flask(__name__)
#app.config.from_object('config.DevelopmentConfig')

app = Flask(__name__)
api = Api(app)

class FastestDockerCI(Resource):

    def __init__(self):
  
        self.events = [ "push", "pull_request" ]
        self.build_queue_dir = os.environ.get("FASTEST_CI_QUEUE_DIR","/var/tmp/docker/fastest-ci/queue")
        self.trigger_id = os.environ["TRIGGER_ID"]
        self.trigger_branch = os.environ["TRIGGER_BRANCH"]
        self.secret = os.environ["TRIGGER_SECRET"]

    def _get_github_ipblocks(self):

        try:
            hooks = requests.get('https://api.github.com/meta').json()["hooks"]
        except:
            msg = "{}".format(requests.get('https://api.github.com/meta').json())
            print msg

        return hooks

    def _check_src_ip(self):

        ipblocks = self._get_github_ipblocks()

        if len(request.access_route) > 1:
            remote_ip = request.access_route[-1]
        else:
            remote_ip = request.access_route[0]

        request_ip = ipaddress.ip_address(u'{0}'.format(remote_ip))

        #results = {}

        # Check if the POST request is from github.com or GHE
        for block in ipblocks:
            if ipaddress.ip_address(request_ip) in ipaddress.ip_network(block):
                print "request_ip = {} is in the list of acceptable ipaddresses".format(request_ip)
                return True

                #results["status"] = True
                #results["request_ip"] = request_ip
                #return results

        msg = "{} is not in list of accepted src ipaddresses".format(request_ip)
        #results["status"] = False
        #results["msg"] = msg
        #return results
        return msg

    def _chk_event(self):

        event = request.headers.get('X-GitHub-Event')
        if event == "ping": return "event is ping - nothing done"
        if event in self.events: return True
        msg = 'event = "{}" must be {}'.format(event,self.events)
        print msg

    def _get_payload_fields(self,**kwargs):

        payload = json.loads(request.data)
  
        event_type = request.headers.get('X-GitHub-Event')
  
        results = {}
  
        if event_type == "push":
            commit_hash = payload["head_commit"]["id"]
            results["message"] = payload["head_commit"]["message"]
            results["author"] = payload["head_commit"]["author"]["name"]
            results["authored_date"] = payload["head_commit"]["timestamp"]
            results["committer"] = payload["head_commit"]["committer"]["name"]
            results["committed_date"] = payload["head_commit"]["timestamp"]
            results["url"] = payload["head_commit"]["url"]
            results["repo_url"] = payload["repository"]["html_url"]
  
            # More fields
            results["compare"] = payload["compare"]
            results["email"] = payload["head_commit"]["author"]["email"]
            results["branch"] = payload["ref"].split("refs/heads/")[1]
  
        if event_type == "pull_request":
            commit_hash = payload["pull_request"]["head"]["sha"]
            results["message"] = payload["pull_request"]["body"]
            results["author"] = payload["pull_request"]["user"]["login"]
            results["url"] = payload["pull_request"]["user"]["url"]
            results["created_at"] = payload["pull_request"]["created_at"]
            results["authored_date"] = payload["pull_request"]["created_at"]
            results["committer"] = None
            results["committed_date"] = None
            results["updated_at"] = payload["pull_request"]["updated_at"]
  
        results["event_type"] = event_type
  
        if event_type == "pull_request" or event_type == "push":
            results["commit_hash"] = commit_hash
            results["status"] = True

            return results
  
        msg = "event_type = {} not allowed".format(event_type)
        results = {"status":False}
        results["msg"] = msg

        return results

    def _check_secret(self):
  
        header_signature = request.headers.get('X-Hub-Signature')
  
        if self.secret is not None and not isinstance(self.secret,six.binary_type):
            self.secret = self.secret.encode('utf-8')
  
        if header_signature is None:
            msg = "header_signature is null"
            return msg
  
        sha_name, signature = header_signature.split('=')
        if sha_name != 'sha1':
            msg = "sha_name needs to be sha1"
            return msg
  
        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(self.secret, msg=request.data, digestmod=sha1)
  
        # Python prior to 2.7.7 does not have hmac.compare_digest
        if hexversion >= 0x020707F0:
            if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
                msg = "Digest does not match signature"
                return msg
        else:
            if not str(mac.hexdigest()) == str(signature):
                msg = "Digest does not match signature"
                return msg
  
        return True

    def _check_trigger_id(self,**kwargs):

        trigger_id = kwargs["trigger_id"]

        if str(trigger_id) != self.trigger_id:
            return "trigger id doesn't match"

        return True

    def _check_trigger_branch(self,**kwargs):

        branch = kwargs.get("branch")

        if str(branch) == str(self.trigger_branch): return True

        msg = "Trigger branch {} does not match branch to test and build on"
        return msg

    def post(self,**kwargs):

        # Check ipaddress
        msg = self._check_src_ip()

        if msg is not True: 
            print msg
            return {"msg":msg}

        print "source ip checked out ok"

        msg = self._check_trigger_id(**kwargs)

        if msg is not True: 
            print msg
            return {"msg":msg}

        print "trigger_id checked out ok"

        msg = self._check_secret()

        if msg is not True: 
            print msg
            return {"msg":msg}

        print "secret checked out ok"

        payload = self._get_payload_fields()

        if msg is not True: 
            print msg
            return {"msg":msg}

        print "payload checked out ok"
     
        msg = self._check_trigger_branch(**payload)

        if msg is not True: 
            print msg
            return {"msg":msg}

        if msg is not True: 
            print msg
            return {"msg":msg}

        print "trigger branch checked out ok"

        filepath = os.path.join(self.build_queue_dir,str(int(time())))

        with open(filepath, 'w') as yaml_file:
            yaml_file.write(yaml.safe_dump(payload,default_flow_style=False))
        print "file written here {}".format(filepath)

api.add_resource(FastestDockerCI, '/<string:trigger_id>')

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=8021,debug=True)
