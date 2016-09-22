## Mimic

FROM ubuntu:16.04
MAINTAINER RCBU <CloudBackup@rackspace.com>

RUN apt-get -qq update && apt-get -qq upgrade && apt-get install -qqy \
    curl \
    python-dev \
    git \
    libev4 \
    libev-dev \
    libffi-dev \
    libssl-dev \
    python-pip \
    python-setuptools

# Get a working version of pip for ubuntu 14.04:
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=744145
RUN /usr/bin/curl -s https://bootstrap.pypa.io/get-pip.py | python

WORKDIR /home/source
RUN git config --global user.email "mimic@docker-local" && git config --global user.name "Docker Mimic"
RUN git clone https://github.com/rackerlabs/mimic .

# Install Mimic
RUN pip install -e .
COPY ./configure_service.sh /home/source/configure_service.sh
COPY ./register_backup_api.py /home/source/register_backup_api.py
COPY ./rc.local.mimic /home/source/rc.local.mimic

EXPOSE 8900
CMD ["./rc.local.mimic"]
