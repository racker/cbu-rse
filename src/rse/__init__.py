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

import pymongo
import moecache

from .rax.http import rawr

from . import config
from . import controllers
from . import util
from .controllers import health_controller
from .controllers import Shared, MainController, HealthController

log = logging.getLogger(__name__)


class RseApplication(rawr.Rawr):
    """RSE app for encapsulating initialization"""

    def __init__(self, conf):
        rawr.Rawr.__init__(self)

        # Do any necessary conversions on the incoming configuration
        def split_mc_nodes(nodes):
            return [util.splitport(n, 11211) for n in nodes]
        conf_converters = {'memcached:servers': split_mc_nodes}
        conf = config.process(conf, conf_converters)

        # Set up backend connections
        cache = self.init_authcache(conf)
        mdb, mdbmaster = self.init_database(conf)

        # Set up routes. This is ugly and I would like to find a better
        # way.
        ctl_shared = controllers.Shared(cache, conf['test_mode'])
        args_health = {
                'mongo_db': mdbmaster,
                'shared': ctl_shared,
                }
        args_main = {
                'mongo_db': mdb,
                'shared': ctl_shared,
                'authtoken_prefix': conf['token_prefix'],
                'token_hashing_threshold': conf['token_hashing_threshold'],
                }
        log.info("Setting up routes")
        self.add_route(r'/health$', controllers.HealthController, args_health)
        self.add_route(r'/.+', controllers.MainController, args_main)

    def init_authcache(self, conf):
        log.info("Initializing auth cache.")

        authtoken_cache = moecache.Client(**conf['memcached'])
        # Force moecache to raise an exception if something is wrong.
        authtoken_cache.stats()
        return authtoken_cache

    def init_database(self, conf):
        log.info("Initializing connection to mongodb.")

        host = conf['mongodb']['host']
        database = conf['mongodb']['database']
        replica_set = conf['mongodb']['replica-set']
        event_ttl = conf['event_ttl']

        log.info("Connecting to mongodb")
        log.debug("mongodb host(s): %s", host)
        log.debug("mongodb DB : %s", database)

        db_connections_ok = False
        for i in range(10):
            try:
                # Master instance connection for the health checker
                log.debug("Establishing db health check connection.")
                connection_master = pymongo.Connection(
                    host,
                    read_preference=pymongo.ReadPreference.PRIMARY
                )
                mongo_db_master = connection_master[database]

                # General connection for regular requests
                # Note: Use one global connection to the DB across all handlers
                # (pymongo manages its own connection pool)
                log.debug("Establishing replica set connection.")
                if not replica_set:
                    connection = pymongo.Connection(
                        host,
                        read_preference=pymongo.ReadPreference.SECONDARY
                    )
                else:
                    try:
                        connection = pymongo.ReplicaSetConnection(
                            host,
                            replicaSet=replica_set,
                            read_preference=pymongo.ReadPreference.SECONDARY
                        )
                    except Exception as ex:
                        log.error(
                            "Mongo connection exception: %s" % (ex.message)
                        )
                        sys.exit(1)

                mongo_db = connection[database]
                mongo_db_master = connection_master[database]
                db_connections_ok = True
                break

            except pymongo.errors.AutoReconnect:
                log.warning(
                    "Got AutoReconnect on startup while attempting to connect "
                    "to DB. Retrying..."
                )
                time.sleep(0.5)

            except Exception as ex:
                log.error(
                    "Error on startup while attempting to connect to DB: " +
                    health_controller.str_utf8(ex)
                )
                sys.exit(1)

        if not db_connections_ok:
            log.error("Could not set up db connections.")
            sys.exit(1)

        # Initialize events collection
        log.info("Initializing events collection.")
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
                log.warning(
                    "Got AutoReconnect on startup while attempting to set up "
                    "events collection. Retrying..."
                )
                time.sleep(0.5)

            except Exception as ex:
                log.error(
                    "Error on startup while attempting to initialize events "
                    "collection: " + health_controller.str_utf8(ex)
                )
                sys.exit(1)

        if not db_events_collection_ok:
            log.error("Could not setup events connections.")
            sys.exit(1)

        return (mongo_db, mongo_db_master)
