FROM ubuntu:16.04
MAINTAINER RCBU <CloudBackup@rackspace.com>

# Update packages
RUN apt-get -qq update && apt-get -qq upgrade && apt-get install -qqy \
    git-core \
    libev4 \
    libev-dev \
    libffi-dev \
    libssl-dev \
    python-dev \
    python-pip \
    python-setuptools

VOLUME /home/rse

# Install dependencies
RUN pip install -U pip
RUN pip install -U \
    gunicorn \
    webob

# rse docker configuration
ADD docker/rse/rse.docker.conf /etc/rse.conf

# Deploy startup script
ADD docker/rse/rse-docker /usr/local/bin/rse-docker
RUN chmod 755 /usr/local/bin/rse-docker

# Install the EOM Logging Config
RUN mkdir -p /etc/eom
ADD etc/logging.conf-sample /etc/eom/logging.conf-sample

# add source and install
ADD . /home/rse
WORKDIR /home/rse
RUN pip install -e .

# finally run
EXPOSE 8000
CMD rse-docker
