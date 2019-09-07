FROM python:3.6-alpine

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn
COPY ./ /opt/api

EXPOSE 8021
ENTRYPOINT ["/opt/api/bin/run.sh"]
