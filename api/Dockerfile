FROM gear2000/jiffy-base:16.04

#FROM elasticdev/ubuntu-18-04-python-3.7

COPY requirements.txt requirements.txt

#./bin/run.py 
#pip install –upgrade python-dotenv
#pip install --upgrade pip
#pip install –upgrade python-dotenv
#pip install python-dotenv
#pip install -r requirements.txt 
#pip uninstall pip
#hash -d pip
#pip install -r requirements.txt 
#pip install –upgrade python-dotenv
#pip install python-dotenv
#./bin/run.py 
#./bin/run.sh
#history
#pip freeze
#history

RUN pip install --upgrade pip 
#RUN hash -d pip
RUN pip install -r requirements.txt
RUN pip install gunicorn
COPY ./ /opt/api
EXPOSE 8021

#FROM python:3.6-alpine
#COPY requirements.txt requirements.txt
#RUN python -m venv venv
#RUN venv/bin/pip install -r requirements.txt
#RUN venv/bin/pip install gunicorn
#COPY ./ /opt/api
#
#EXPOSE 8021
#ENTRYPOINT ["/opt/api/bin/run.sh"]
