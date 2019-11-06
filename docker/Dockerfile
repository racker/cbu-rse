# RSE local dev testing setup

FROM ubuntu:latest

# Install required APT packages. RSE looks at localhost for
# mongo/memcache by default, so keeping them in the same container
# simplifies configuration.
#
# The loop is there to deal with intermittent network failures that
# would otherwise break this step. Yes, it's ugly. Sorry.

COPY ./deps/*.apt.txt /root/deps/
RUN cat /root/deps/*.apt.txt | grep -v ^# > /root/install.apt.txt
RUN apt-get update && \
    until apt-get install -y $(cat /root/install.apt.txt) \
    ; do sleep 2; done

# Install RSE
ADD . /root/rse
WORKDIR /root/rse
RUN pip install .

# Configure nginx
COPY ./docker/nginx.rse.conf /etc/nginx/sites-enabled/default

WORKDIR /root
EXPOSE 8000
ENTRYPOINT ["/root/rse/docker/start.sh"]
