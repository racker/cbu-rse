# RSE local dev testing setup

FROM ubuntu:latest

# Some of our devs run windows, and dockerfile COPY has no inherent
# line-ending correction, so we need to do it on the far end when needed.
# Install dos2unix for the purpose. This should really be part of build, not
# here, but blah.

RUN apt-get update && apt-get install -y dos2unix

# Install required APT packages. Copying only the sysdeps files here
# ensures that the cache for this step is only invalidated if the APT
# dependencies actually change, which should not happen often. The loop
# is there to deal with intermittent network failures that would
# otherwise break this step.  Yes, it's ugly. Sorry.

COPY ./deps/*.apt.txt /root/deps/
RUN dos2unix /root/deps/*.apt.txt

RUN cat /root/deps/*.apt.txt | grep -v ^# > /root/install.apt.txt
RUN until apt-get install -y $(cat /root/install.apt.txt) \
    ; do echo "apt-get failed, retrying in 2s"; sleep 2; done

# Install RSE
ADD . /root/rse
WORKDIR /root/rse
COPY ./deps/*.pip.txt /root/deps/
RUN dos2unix /root/deps/*.pip.txt
RUN pip3 install -r /root/deps/docker.pip.txt
RUN pip3 install .

# Configure nginx
COPY ./docker/nginx.rse.conf /etc/nginx/sites-enabled/default

RUN dos2unix /root/rse/docker/start.sh
WORKDIR /root
EXPOSE 8000
ENTRYPOINT ["/root/rse/docker/start.sh"]
