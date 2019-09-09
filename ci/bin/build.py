#!/usr/bin/python

#import json
import os
import yaml
from time import sleep

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
        
        file_path = self._get_next_build()
        if not file_path: return

        try:
            yaml_str = open(file_path,'r').read()
            loaded_yaml = dict(yaml.load(yaml_str))
        except:
            print "WARN: could not load yaml at {} - skipping build".format(file_path)
            return

        print 'b'*32
        print 'b'*32
        print loaded_yaml
        print 'b'*32
        print 'b'*32

    def run(self):

        while True:
            self.run()
            sleep(1)

    def _get_payload_fields(self,**kwargs):

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

        return results

if __name__ == "__main__":
    main = LocalDockerCI()
    main.run()
