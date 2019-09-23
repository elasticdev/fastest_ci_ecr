#!/bin/bash

cd /tmp
git clone -b master https://github.com/elasticdev/host_reporter_helper.git
cd host_reporter_helper
./reinstall_pkg_dev.sh 
cd /tmp
rm -rf host_reporter_helper
