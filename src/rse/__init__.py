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

import argparse
import logging
import logging.handlers
import os
import os.path
import sys
import time
import ConfigParser

from eom import auth
from eom import bastion
from oslo_config import cfg
import pymongo
from rax.http import rawr

from controllers import shared
from controllers import health_controller
from controllers import main_controller


class RseApplication(rawr.Rawr):
    """RSE app for encapsulating initialization"""

    def __init__(self):
        rawr.Rawr.__init__(self)

        # Initialize config paths
        dir_path = os.path.dirname(os.path.abspath(__file__))
        local_config_path = os.path.join(dir_path, 'rse.conf')
        global_config_path = '/etc/rse.conf'
        global_config_dir_path = '/etc/rse/rse.conf'
        default_config_path = os.path.join(dir_path, 'rse.default.conf')

        # Parse options
        config = ConfigParser.ConfigParser(
            defaults={
                'timeout': '5',
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
        elif os.path.exists(global_config_dir_path):
            config.read(global_config_dir_path)

        # Add the log message handler to the logger
        # Set up a specific logger with our desired output level
        logger = logging.getLogger(__name__)
        logger.setLevel(
            logging.DEBUG
            if config.get('logging', 'verbose')
            else logging.WARNING
        )

        formatter = logging.Formatter(
            '%(asctime)s - RSE - PID %(process)d - %(funcName)s:%(lineno)d - '
            '%(levelname)s - %(message)s'
        )

        if config.getboolean('logging', 'console'):
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if config.getboolean('logging', 'filelog'):
            handler = logging.handlers.RotatingFileHandler(
                config.get('logging', 'filelog-path'),
                maxBytes=5 * 1024 * 1024,
                backupCount=5
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if config.getboolean('logging', 'syslog'):
            handler = logging.handlers.SysLogHandler(
                address=config.get('logging', 'syslog-address')
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Connnect to MongoDB
        mongo_db, mongo_db_master = self.init_database(logger, config)

        # Get auth requirements
        test_mode = config.getboolean('rse', 'test')

        # Setup routes
        shared_controller = Shared(logger)

        health_options = dict(shared=shared_controller,
                              mongo_db=mongo_db_master,
                              test_mode=test_mode)
        self.add_route(
            r"/health$",
            health_controller.HealthController,
            health_options
        )

        main_options = dict(shared=shared_controller,
                            mongo_db=mongo_db,
                            test_mode=test_mode)
        self.add_route(r"/.+", main_controller.MainController, main_options)

        logger.info("RSE Initialization completed.")

    def init_database(self, logger, config):
        logger.info("Initializing connection to mongodb.")

        event_ttl = config.getint('rse', 'event-ttl')
        mongo_uri = config.get('mongodb', 'uri')
        db_name = config.get('mongodb', 'database')
        use_ssl = config.getboolean('mongodb', 'use_ssl')

        db_connections_ok = False
        for _ in range(10):
            try:
                # Master instance connection for the health checker
                logger.debug("Establishing db health check connection.")
                connection_master = pymongo.MongoClient(
                    mongo_uri,
                    read_preference=pymongo.ReadPreference.PRIMARY,
                    ssl=use_ssl
                )
                mongo_db_master = connection_master[db_name]

                # General connection for regular requests
                # Note: Use one global connection to the DB across all handlers
                # (pymongo manages its own connection pool)
                logger.debug("Establishing replica set connection.")
                replica_set = config.get('mongodb', 'replica-set')
                if replica_set == '[none]':
                    connection = pymongo.MongoClient(
                        mongo_uri,
                        read_preference=pymongo.ReadPreference.SECONDARY,
                        ssl=use_ssl
                    )
                else:
                    try:
                        connection = pymongo.MongoClient(
                            mongo_uri,
                            replicaSet=replica_set,
                            read_preference=pymongo.ReadPreference.SECONDARY,
                            ssl=use_ssl
                        )
                    except Exception as ex:
                        logger.error(
                            "Mongo connection exception: %s" % (ex.message)
                        )
                        sys.exit(1)

                mongo_db = connection[db_name]
                mongo_db_master = connection_master[db_name]
                db_connections_ok = True
                break

            except pymongo.errors.AutoReconnect:
                logger.warning(
                    "Got AutoReconnect on startup while attempting to connect "
                    "to DB. Retrying..."
                )
                time.sleep(0.5)

            except Exception as ex:
                logger.error(
                    "Error on startup while attempting to connect to DB: " +
                    health_controller.str_utf8(ex)
                )
                sys.exit(1)

        if not db_connections_ok:
            logger.error("Could not set up db connections.")
            sys.exit(1)

        # Initialize events collection
        logger.info("Initializing events collection.")
        db_events_collection_ok = False
        for _ in range(10):
            try:
                # Order matters - want exact matches first, and ones that will
                # pare down the result set the fastest
                # NOTE: MongoDB does not use multiple indexes per query, so we
                # want to put all query fields in the index.
                mongo_db_master.events.ensure_index(
                    [
                        ('channel', pymongo.ASCENDING),
                        ('_id', pymongo.ASCENDING),
                        ('uuid', pymongo.ASCENDING)
                    ],
                    name='get_events'
                )

                # Drop TTL index if a different number of seconds was requested
                index_info = mongo_db_master.events.index_information()

                if 'ttl' in index_info:
                    index = index_info['ttl']
                    if (
                        ('expireAfterSeconds' not in index) or
                        index['expireAfterSeconds'] != event_ttl
                    ):
                        mongo_db_master.events.drop_index('ttl')

                mongo_db_master.events.ensure_index(
                    'created_at', expireAfterSeconds=event_ttl, name='ttl')

                # WARNING: Counter must start at a value greater than 0 per the
                # RSE spec, so we set to 0 since the id generation logic always
                # adds one to get the next id, so we will start at 1 for the
                # first event
                if not mongo_db_master.counters.find_one(
                    {'_id': 'last_known_id'}
                ):
                    mongo_db_master.counters.insert(
                        {'_id': 'last_known_id', 'c': 0})

                db_events_collection_ok = True
                break

            except pymongo.errors.AutoReconnect:
                logger.warning(
                    "Got AutoReconnect on startup while attempting to set up "
                    "events collection. Retrying..."
                )
                time.sleep(0.5)

            except Exception as ex:
                logger.error(
                    "Error on startup while attempting to initialize events "
                    "collection: " + health_controller.str_utf8(ex)
                )
                sys.exit(1)

        if not db_events_collection_ok:
            logger.error("Could not setup events connections.")
            sys.exit(1)

        return (mongo_db, mongo_db_master)

def instantiate():
    """ Initialize a wsgi callable for use by gunicorn """

    rse_app = RseApplication()

    rse_conf = cfg.CONF
    rse_conf(project='rse', args=[])
    auth.configure(rse_conf)
    bastion.configure(rse_conf)

    auth_redis_client = auth.get_auth_redis_client()

    auth_app = auth.wrap(rse_app, auth_redis_client)
    app = bastion.wrap(rse_app, auth_app)
    return app
