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

# SSH Settings
RUN mkdir -p /root/.ssh
ADD ./id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts

# Install dependencies
RUN pip install -U pip
RUN pip install -U \
    blist \
    cassandra-driver \
    gevent \
    gunicorn \
    moecache \
    pymongo==2.4 \
    webob

# rse-util
RUN mkdir -p /home/rse-util
RUN git clone git@github.com:rackerlabs/rse-util.git /home/rse-util
RUN pip install -e /home/rse-util

# rse
RUN mkdir -p /home/rse
ADD . /home/rse

# rse configurations
ADD rse.docker.conf /etc/rse.conf

EXPOSE 8000

WORKDIR /home/rse
CMD ["gunicorn", "rse:app", "-b", "0.0.0.0:8000", "--log-file", "-", "--log-level", "debug"]
