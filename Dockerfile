FROM ubuntu:latest
MAINTAINER John Heatherington <john.heatherington@rackspace.com>

# Update packages
RUN apt-get -qq update
RUN apt-get -qq upgrade

# Update packages
RUN apt-get install -y \
    curl \
    git-core \
    python-dev \
    python-pip \
    python-setuptools \
    telnet

# Install dependencies
RUN pip install -U pip
RUN pip install -U \
    blist \
    gevent \
    gunicorn \
    moecache \
    pymongo==2.4 \
    webob

# rse-util
ADD ./rse-util /home/rse-util
RUN pip install -e /home/rse-util

# rse
ADD . /home/rse

# rse configurations
ADD rse.docker.conf /etc/rse.conf

EXPOSE 8000

WORKDIR /home/rse
CMD ["gunicorn", "rse:app", "-b", "0.0.0.0:8000", "--log-file", "-", "--log-level", "debug"]
