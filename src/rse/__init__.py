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

import sys
import time
import logging
import logging.handlers

import pymongo
import moecache

from .rax.http import rawr

from . import config
from . import controllers
from . import util
from .controllers import shared
from .controllers import health_controller

logger = logging.getLogger(__name__)


class RseApplication(rawr.Rawr):
    """RSE app for encapsulating initialization"""

    def __init__(self, conf):
        rawr.Rawr.__init__(self)

        # Do any necessary conversions on the incoming configuration
        def split_mc_nodes(nodes):
            return [util.splitport(n, 11211) for n in nodes]
        conf_converters = {'memcached:servers': split_mc_nodes}
        conf = config.process(conf, conf_converters)

        # FastCache for Auth Token
        authtoken_cache = moecache.Client(**conf['memcached'])

        # Connnect to MongoDB
        mongo_db, mongo_db_master = self.init_database(logger, conf)

        # Setup routes
        shared_controller = shared.Shared(logger,
                                          authtoken_cache,
                                          **conf['shared'])
        for routeid, settings in sorted(conf['routes'].items()):
            logger.info("Adding route: %s", routeid)
            pattern = settings['pattern']
            controller = getattr(controllers, settings['controller'])
            kwargs = dict(shared=shared_controller,
                          mongo_db=mongo_db_master,
                          **settings['args'])
            self.add_route(pattern, controller, kwargs)
        logger.info("RSE Initialization completed.")

    def init_database(self, logger, conf):
        logger.info("Initializing connection to mongodb.")

        uri = conf['mongodb']['uri']
        database = conf['mongodb']['database']
        replica_set = conf['mongodb']['replica-set']
        event_ttl = conf['mongodb']['event-ttl']

        logger.info("Connecting to mongodb:%s:%s", uri, database)

        db_connections_ok = False
        for i in range(10):
            try:
                # Master instance connection for the health checker
                logger.debug("Establishing db health check connection.")
                connection_master = pymongo.Connection(
                    uri,
                    read_preference=pymongo.ReadPreference.PRIMARY
                )
                mongo_db_master = connection_master[database]

                # General connection for regular requests
                # Note: Use one global connection to the DB across all handlers
                # (pymongo manages its own connection pool)
                logger.debug("Establishing replica set connection.")
                if replica_set == '[none]':
                    connection = pymongo.Connection(
                        uri,
                        read_preference=pymongo.ReadPreference.SECONDARY
                    )
                else:
                    try:
                        connection = pymongo.ReplicaSetConnection(
                            uri,
                            replicaSet=replica_set,
                            read_preference=pymongo.ReadPreference.SECONDARY
                        )
                    except Exception as ex:
                        logger.error(
                            "Mongo connection exception: %s" % (ex.message)
                        )
                        sys.exit(1)

                mongo_db = connection[database]
                mongo_db_master = connection_master[database]
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
        for i in range(10):
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
