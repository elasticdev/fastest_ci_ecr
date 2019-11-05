FROM gear2000/jiffy-base:16.04

#FROM elasticdev/ubuntu-18-04-python-3.7

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip 
RUN pip install -r requirements.txt
#COPY install_trivy_ubuntu.sh /opt/
COPY install-edreporterhelper.sh /opt/
#RUN chmod 755 /opt/install_trivy_ubuntu.sh && chmod 755 /opt/install-edreporterhelper.sh 
RUN chmod 755 /opt/install-edreporterhelper.sh 
RUN /opt/install-edreporterhelper.sh
RUN apt-get update && apt-get install wget apt-transport-https gnupg lsb-release apt-transport-https ca-certificates -y
RUN wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add - && \
    echo deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main | tee -a /etc/apt/sources.list.d/trivy.list
RUN apt-cache search trivy 
#RUN apt-cache search trivy && apt-get install trivy -y
#RUN /opt/install_trivy_ubuntu.sh 
COPY bin /opt/

#FROM python:3.6-alpine
#COPY requirements.txt requirements.txt
#RUN python -m venv venv
#RUN venv/bin/pip install -r requirements.txt
#RUN venv/bin/pip install gunicorn
