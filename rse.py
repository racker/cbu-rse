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
            defaults={
                'timeout': '5',
                'authtoken-retention-period': '30',
                'authtoken-slice-size': '2',
                'replica-set': '[none]',
                'filelog': 'yes',
                'console': 'no',
                'syslog': 'no',
                'event-ttl': '120'
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
        logger.setLevel(logging.DEBUG if config.get(
            'logging', 'verbose') else logging.WARNING)

        formatter = logging.Formatter(
            '%(asctime)s - RSE - PID %(process)d - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s')

        if config.getboolean('logging', 'console'):
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if config.getboolean('logging', 'filelog'):
            handler = logging.handlers.RotatingFileHandler(
                config.get('logging', 'filelog-path'), maxBytes=5 * 1024 * 1024, backupCount=5)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if config.getboolean('logging', 'syslog'):
            handler = logging.handlers.SysLogHandler(
                address=config.get('logging', 'syslog-address'))
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # FastCache for Auth Token
        retention_period = config.getint(
            'fastcache', 'authtoken-retention-period')
        slice_size = config.getint('fastcache', 'authtoken-slice-size')
        authtoken_cache = FastCache(retention_period, slice_size)

        # Connnect to MongoDB
        mongo_db, mongo_db_master = self.init_database(logger, config)

        # Get account services options
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

    def init_database(self, logger, config):
        event_ttl = config.getint('rse', 'event-ttl')

        db_connections_ok = False
        for i in range(10):
            try:
                # Master instance connection for the health checker
                connection_master = pymongo.Connection(
                    config.get('mongodb', 'uri'), read_preference=pymongo.ReadPreference.PRIMARY)
                mongo_db_master = connection_master[
                    config.get('mongodb', 'database')]

                # General connection for regular requests
                # Note: Use one global connection to the DB across all handlers
                # (pymongo manages its own connection pool)
                replica_set = config.get('mongodb', 'replica-set')
                if replica_set == '[none]':
                    connection = pymongo.Connection(
                        config.get('mongodb', 'uri'), read_preference=pymongo.ReadPreference.SECONDARY)
                else:
                    try:
                        connection = pymongo.ReplicaSetConnection(
                            config.get('mongodb', 'uri'), replicaSet=replica_set, read_preference=pymongo.ReadPreference.SECONDARY)
                    except Exception as ex:
                        logger.error(
                            "Mongo connection exception: %s" % (ex.message))
                        sys.exit(1)

                mongo_db = connection[config.get('mongodb', 'database')]
                mongo_db_master = connection_master[
                    config.get('mongodb', 'database')]
                db_connections_ok = True

            except pymongo.errors.AutoReconnect:
                logger.warning(
                    "Got AutoReconnect on startup while attempting to connect to DB. Retrying...")
                time.sleep(0.5)

            except Exception as ex:
                logger.error(
                    "Error on startup while attempting to connect to DB: " + str_utf8(ex))
                sys.exit(1)

        if not db_connections_ok:
            logger.error("Could not set up db connections")
            sys.exit(1)

        # Initialize events collection
        db_events_collection_ok = False
        for i in range(10):
            try:
                # get rid of deprecated indexes so they don't bloat our working
                # set size
                try:
                    mongo_db_master.events.drop_index('uuid_1_channel_1')
                except pymongo.errors.OperationFailure:
                    # Index already deleted
                    pass

                try:
                    mongo_db_master.events.drop_index('created_at_1')
                except pymongo.errors.OperationFailure:
                    # Index already deleted
                    pass

                # Order matters - want exact matches first, and ones that will pair down the result set the fastest
                # NOTE: MongoDB does not use multiple indexes per query, so we want to put all query fields in the
                # index.
                mongo_db_master.events.ensure_index(
                    [('channel', pymongo.ASCENDING), ('_id', pymongo.ASCENDING), ('uuid', pymongo.ASCENDING)], name='get_events')

                # Drop TTL index if a different number of seconds was requested
                index_info = mongo_db_master.events.index_information()

                if 'ttl' in index_info:
                    index = index_info['ttl']
                    if ('expireAfterSeconds' not in index) or index['expireAfterSeconds'] != event_ttl:
                        mongo_db_master.events.drop_index('ttl')

                mongo_db_master.events.ensure_index(
                    'created_at', expireAfterSeconds=event_ttl, name='ttl')

                # WARNING: Counter must start at a value greater than 0 per the RSE spec, so
                # we set to 0 since the id generation logic always adds one to get
                # the next id, so we will start at 1 for the first event
                if not mongo_db_master.counters.find_one({'_id': 'last_known_id'}):
                    mongo_db_master.counters.insert(
                        {'_id': 'last_known_id', 'c': 0})

                db_events_collection_ok = True
                break

            except pymongo.errors.AutoReconnect:
                logger.warning(
                    "Got AutoReconnect on startup while attempting to set up events collection. Retrying...")
                time.sleep(0.5)

            except Exception as ex:
                logger.error(
                    "Error on startup while attempting to initialize events collection: " + str_utf8(ex))
                sys.exit(1)

        if not db_events_collection_ok:
            logger.error("Could not setup events connections")
            sys.exit(1)

        return (mongo_db, mongo_db_master)

# WSGI app
app = RseApplication()

# If running this script directly, startup a basic WSGI server for testing
if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    httpd = make_server('', 8000, app)
    print "Serving on port 8000..."
    httpd.serve_forever()
