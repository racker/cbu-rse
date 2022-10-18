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

import logging

import pymongo
import moecache
from tenacity import retry
from tenacity import stop_after_attempt as saa
from tenacity import wait_fixed as wait
from tenacity import retry_if_exception_type as extype
from tenacity import before_sleep_log as bsl
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure

from .rax.http import rawr

from . import config
from . import controllers
from . import util
from .instrumentation import nr

log = logging.getLogger(__name__)


class RseApplication(rawr.Rawr):
    """RSE app for encapsulating initialization"""

    def __init__(self, conf):
        rawr.Rawr.__init__(self)

        log.info("Processing configuration")

        def split_mc_nodes(nodes):
            return [util.splitport(n, 11211) for n in nodes]

        conf_converters = {'memcached:servers': split_mc_nodes}
        self.conf = conf = config.process(conf, conf_converters)

        log.info("Connecting to memcache")
        cache = moecache.Client(**conf['memcached'])
        # Force moecache to raise an exception if something is wrong.
        log.debug("Cache check: %s : %s", "_key_", cache.get("_key_"))

        log.info("Connecting to mongo")
        dbname = conf['database']
        mc_primary, mc_secondary = self._init_mongo(**conf['mongodb'])
        db_primary = mc_primary[dbname]
        db_secondary = mc_secondary[dbname]

        log.info("Initializing events collection")
        self._init_events(db_primary, conf['event_ttl'], conf['first_event'])

        log.info("Setting up routes")
        # This is ugly and I would like to find a better way.
        ctl_shared = controllers.Shared(cache, conf['test_mode'])
        args_health = {
                'mongo_db': db_primary,
                'shared': ctl_shared,
                'fields': conf['health_fields'],
                }
        args_main = {
                'mongo_db': db_secondary,
                'shared': ctl_shared,
                'authtoken_prefix': conf['token_prefix'],
                'token_hashing_threshold': conf['token_hashing_threshold'],
                }
        self.add_route(r'/health$', controllers.HealthController, args_health)
        self.add_route(r'/.+', controllers.MainController, args_main)

    @retry(stop=saa(5), wait=wait(5), retry=extype(ConnectionFailure), before_sleep=bsl(log, logging.WARN))
    def _init_mongo(self, **settings):
        """ Wrapper for mongo connection setup.

        This will try several times before giving up.
        """
        return [MongoClient(readPreference=pref, **settings)
                for pref in ['primary', 'secondary']]

    def __call__(self, environ, start_response):
        req = rawr.Request(environ)
        if self.conf['newrelic']['record_ip']:
            nr.add_custom_parameter('source', req.client_addr)
        for header in self.conf['newrelic']['record_headers']:
            value = req.headers.get(header, 'unknown')
            nr.add_custom_parameter('request.headers.' + header, value)
        return super().__call__(environ, start_response)

    @retry(stop=saa(10), wait=wait(0.5), retry=extype(AutoReconnect))
    def _init_events(self, db, ttl, first_event=0):
        """ Initialize the events collection if needed

        `db` should be a mongo database connected with readpref: primary.
        (FIXME: does it need to be? If it does, check and fail)
        `ttl` should be the event TTL from the config.
        `first_event` is the starting event ID when initializing the DB
            for the first time. It is ignored if the ID counter already
            exists.
        """

        # Create indexes. Order matters - want exact matches first, and
        # ones that will pare down the result set the fastest. NOTE:
        # MongoDB does not use multiple indexes per query, so we want to
        # put all query fields in the index.
        index_keys = [('channel', pymongo.ASCENDING),
                      ('_id', pymongo.ASCENDING),
                      ('uuid', pymongo.ASCENDING)]
        db.events.create_index(index_keys, name='get_events')

        # Set up the TTL index. If it doesn't exist, create it. If it
        # does exist but the TTL has changed, drop it first.
        index_info = db.events.index_information()
        if 'ttl' in index_info:
            old_ttl = index_info['ttl'].get('expireAfterSeconds', None)
            if old_ttl != ttl:
                db.events.drop_index('ttl')
        db.events.create_index('created_at', name='ttl',
                               expireAfterSeconds=ttl)

        # NOTE: Event IDs must be >0 per the RSE spec. However, the id
        # generation logic adds 1 to get the next ID, so starting at 0
        # by default is fine.
        ct_evt = db.counters.find_one({'_id': 'last_known_id'})
        if ct_evt:
            log.debug("fallback counter present, value: %s", ct_evt['c'])
        else:
            msg = "event counter not present, initializing it to %s"
            log.info(msg, first_event)
            db.counters.insert({'_id': 'last_known_id', 'c': first_event})
