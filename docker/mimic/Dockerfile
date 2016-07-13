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
# Until Mimic merges the related PRs we will have to use BenjamenMeyer's branch
#RUN git clone https://github.com/rackerlabs/mimic .
RUN git clone https://github.com/BenjamenMeyer/mimic .
# Mimic: Support APIs not hosted by Mimic:
RUN git checkout enhancement_internal-external_urls
# Mimic: Add Cloud Backup to the special accounts (merged)
#RUN git merge origin/enhancement_cloudbackup_service
# Mimic: Bug Fix Validating Tokens (merged)
#RUN git merge origin/bugfix_validate_token_for_repose
# Mimic: List API Key in the generic case (merged)
#RUN git merge origin/enhancement_osksadm_credentials_also
# Mimic: Swift in multiple data centers (merged)
#RUN git merge origin/enhancement_swift_in_dfw
# Mimic: Swift diagnostics
RUN git merge origin/bugfix_swift_object_paths
# Mimic: Swift Head container/object support
RUN git merge origin/bugfix_swift_head_operations
# Mimic: Default Region for User
RUN git merge origin/enhancement_default_region

# Install Mimic
RUN pip install -e .
#RUN pip install -r requirements.txt
COPY ./configure_service.sh /home/source/configure_service.sh
COPY ./register_backup_api.py /home/source/register_backup_api.py
COPY ./rc.local.mimic /home/source/rc.local.mimic

EXPOSE 8900
CMD ["./rc.local.mimic"]
