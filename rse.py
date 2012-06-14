#!/usr/bin/env python

"""
@file rse.py
@author Kurt Griffiths, Xuan Yu, et al.
$Author$  <=== populated-by-subversion
$Revision$  <=== populated-by-subversion
$Date$  <=== populated-by-subversion

@brief
Rackspace RSE Server. Run with -h for command-line options.

@pre
Servers have syncronized clocks (ntpd).
Python 2.7 with the following installed: pymongo, webob, and argparse
ulimit -n 4096 # or better
sysctl -w net.core.somaxconn="4096" # or better
"""

import os
import sys
import time
import logging
import logging.handlers
import os.path
import ConfigParser
import io
import httplib

# Requires python 2.6 or better
import json

# These need to be installed (easy_install)
import pymongo
import argparse

from rax.http import rawr
from rax.fastcache.fastcache import *

from controllers.shared import *
from controllers.health_controller import *
from controllers.main_controller import *


class RseApplication(rawr.Rawr):
  """RSE app for encapsulating initialization"""

  def __init__(self):
    rawr.Rawr.__init__(self)

    # Initialize config paths
    dir_path = os.path.dirname(os.path.abspath(__file__))
    local_config_path = os.path.join(dir_path, 'rse.conf')
    global_config_path = '/etc/rse.conf'
    default_config_path = os.path.join(dir_path, 'rse.default.conf')

    # Parse options
    config = ConfigParser.ConfigParser(
      defaults = {
        'timeout': '5',
        'authtoken_retention_period': '30',
        'authtoken_slice_size': '2',
        'replica-set': '[none]'
      }
    )

    config.read(default_config_path)

    if os.path.exists(local_config_path):
       config.read(local_config_path)
    elif os.path.exists(global_config_path):
       config.read(global_config_path)

    # Add the log message handler to the logger
    # Set up a specific logger with our desired output level
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if config.get('logging', 'verbose') else logging.WARNING)

    formatter = logging.Formatter('%(asctime)s - RSE - PID %(process)d - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s')

    if config.getboolean('logging', 'filelog'):
      handler = logging.handlers.RotatingFileHandler(config.get('logging', 'filelog-path'), maxBytes=5 * 1024*1024, backupCount=5)
      handler.setFormatter(formatter);
      logger.addHandler(handler)

    if config.getboolean('logging', 'syslog'):
      handler = logging.handlers.SysLogHandler(address=config.get('logging', 'syslog-address'))
      handler.setFormatter(formatter);
      logger.addHandler(handler)

    # FastCache for Auth Token
    retention_period = config.getint('fastcache', 'authtoken-retention-period')
    slice_size = config.getint('fastcache', 'authtoken-slice-size')
    authtoken_cache = FastCache(retention_period, slice_size)

    # Master instance connection for the health checker
    connection_master = pymongo.Connection(config.get('mongodb', 'uri'), read_preference=pymongo.ReadPreference.PRIMARY)
    mongo_db_master = connection_master[config.get('mongodb', 'database')]

    # General connection for regular requests
    # Note: Use one global connection to the DB across all handlers (pymongo manages its own connection pool)
    replica_set = config.get('mongodb', 'replica-set')
    if replica_set == '[none]':
      connection = pymongo.Connection(config.get('mongodb', 'uri'), read_preference=pymongo.ReadPreference.SECONDARY)
    else:
      try:
        connection = pymongo.ReplicaSetConnection(config.get('mongodb', 'uri'), replicaSet=replica_set, read_preference=pymongo.ReadPreference.SECONDARY)
      except Exception as ex:
        logger.warning( "Mongo connection exception: %s" % (ex.message))
        if ex.message == 'secondary':
          return

    mongo_db = connection[config.get('mongodb', 'database')]

    # Initialize collections
    for i in range(10):
      try:
        mongo_db.events.ensure_index([('uuid', pymongo.ASCENDING), ('channel', pymongo.ASCENDING)])
        mongo_db.events.ensure_index('created_at', pymongo.ASCENDING)
        break
      except pymongo.errors.AutoReconnect:
        time.sleep(1)

    # WARNING: Counter must start at a value greater than 0 per the RSE spec!
    if not mongo_db.counters.find_one({'_id': 'last_known_id'}):
      mongo_db.counters.insert({'_id': 'last_known_id', 'c': 0})

    accountsvc_host = config.get('account-services', 'host')
    accountsvc_https = config.getboolean('account-services', 'https')
    accountsvc_timeout = config.getint('account-services', 'timeout')
    test_mode = config.getboolean('rse', 'test')

    # Setup routes
    shared = Shared(logger, authtoken_cache)

    health_options = dict(shared=shared, accountsvc_host=accountsvc_host,
                          accountsvc_https=accountsvc_https,
                          accountsvc_timeout=accountsvc_timeout,
                          mongo_db=mongo_db_master, test_mode=test_mode)
    self.add_route(r"/health$", HealthController, health_options)

    main_options = dict(shared=shared, accountsvc_host=accountsvc_host,
                        accountsvc_https=accountsvc_https,
                        accountsvc_timeout=accountsvc_timeout,
                        mongo_db=mongo_db, test_mode=test_mode)
    self.add_route(r"/.+", MainController, main_options)

# WSGI app
app = RseApplication()

# If running this script directly, startup a basic WSGI server for testing
if __name__ == "__main__":
  from wsgiref.simple_server import make_server

  httpd = make_server('', 8000, app)
  print "Serving on port 8000..."
  httpd.serve_forever()

