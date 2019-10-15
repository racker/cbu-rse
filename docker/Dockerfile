# RSE local dev testing setup

FROM ubuntu:latest

# Install required APT packages. RSE looks at localhost for
# mongo/memcache by default, so keeping them in the same container
# simplifies configuration.
#
# The loop is there to deal with intermittent network failures that
# would otherwise break this step. Yes, it's ugly. Sorry.

RUN apt-get update && \
    until apt-get install -y \
    python-dev \
    python-pip \
    python-setuptools \
    memcached \
    mongodb \
    nginx \
    ; do sleep 2; done

# Install RSE
ADD . /root/rse
WORKDIR /root/rse
RUN pip install .

# Configure nginx
COPY ./docker/nginx.rse.conf /etc/nginx/sites-enabled/default

WORKDIR /root
EXPOSE 8000
CMD service nginx restart && rse
