#!/bin/sh

#export ENV_VAR=${ENV_VAR:="app"}
#export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${JIFFY_SAAS_HOME_DIR}:${JIFFY_SAAS_HOME_DIR}/bin:${JIFFY_SAAS_HOME_DIR}/sbin
#export CPUS=`cat /proc/cpuinfo |grep processor | wc -l`
#export THREADS=4
#
#if [ $ENV_VAR == "dev" ]
#then
#    export THREADS=4
#fi
#
#if [ $ENV_VAR == "app" ]
#then
#    export THREADS=16
#fi
#
#export THREADS=2
#
#gunicorn -w $THREADS -t 900 -b :8021 run:app

#source venv/bin/activate
#gunicorn -b :8021 --access-logfile - --error-logfile - run:app

export THREADS=2
export APP_HOME=/opt/api
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${APP_HOME}/bin:${APP_HOME}/sbin
export caller="api"
cd $APP_HOME/bin
gunicorn -w $THREADS -t 120 -b :8021 --access-logfile - --error-logfile - run:app
