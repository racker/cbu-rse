"""
@file health_controller.py
@author Kurt Griffiths, Xuan Yu, et al.

@brief
Health controller for Rackspace RSE Server.
"""

import datetime
import time
import httplib

import json

import pymongo

from rax.http.exceptions import *
from rax.http import rawr

from .shared import *


def str_utf8(instr):
    # @todo Move this into raxPy, give namespace
    return unicode(instr).encode("utf-8")


def format_datetime(dt):
    # @todo Move this into raxPy, put inside a namespace
    """Formats a datetime instance according to ISO 8601-Extended"""
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


class HealthController(rawr.Controller):
    """Provides web service health info"""
    """@todo Move this class into a separate file"""

    def __init__(self, mongo_db, test_mode, shared):
        self.mongo_db = mongo_db  # MongoDB database for storing events
        # MongoDB connection for storing events
        self.mongo_db_connection = mongo_db.connection
        self.test_mode = test_mode  # If true, relax auth/uuid requirements
        self.shared = shared  # Shared performance counters, logging, etc.

    def _basic_health_check(self):
        db_ok = False

        for retry_counter in xrange(10):
            try:
                # Important: This must work on secondaries (e.g., read-only
                # slaves)
                self.mongo_db.events.count()
                db_ok = True
                break
            except pymongo.errors.AutoReconnect:
                self.shared.logger.error(
                    "AutoReconnect caught from events.count() in health check. Retrying...")
            except Exception as ex:
                self.shared.logger.error(
                    'Could not count events collection: ' + str_utf8(ex))
                break

        return db_ok

    def _create_report(self, profile_db, validate_db):
        """@todo Build up the report piecemeal so we can get partial results on errors."""
        """@todo Return a non-200 HTTP error code on error"""

        validation_info = "N/A. Pass validate_db=true to enable."
        profile_info = "N/A. Pass profile_db=true to enable."
        server_info = "N/A."
        db_error_message = "N/A"

        for retry_counter in xrange(10):
            try:
                # dbstats is in JSON format. Retrieve individual item like
                # dbstats['globalLock']['currentQueue']
                # dbstats = self.mongo_db.command("serverStatus")
                dbstats = self.mongo_db.server_info()

                # Collection stats is in JSON format. docu on stat items:
                # http://www.mongodb.org/display/DOCS/collStats+Command
                # collstats_events = self.mongo_db.command(
                #    {"collStats": "events"})
                collstats_events = self.mongo_db.rse.command("collstats", "events")

                max_event = self.mongo_db.events.find_one(
                    sort=[('created_at', pymongo.ASCENDING)])

                collstats_max_event_info = {}
                if max_event:
                    collstats_max_event_info[
                        'created_at'] = format_datetime(max_event['created_at'])
                    collstats_max_event_info['age'] = (
                        datetime.datetime.utcnow() - max_event['created_at']).seconds

                    event_data = json.loads(max_event['data'])
                    if 'Event' in event_data:
                        collstats_max_event_info['name'] = event_data['Event']
                    else:
                        collstats_max_event_info['name'] = 'N/A'

                min_event = self.mongo_db.events.find_one(
                    sort=[('created_at', pymongo.DESCENDING)])

                collstats_min_event_info = {}
                if min_event:
                    collstats_min_event_info[
                        'created_at'] = format_datetime(min_event['created_at'])
                    collstats_min_event_info['age'] = (
                        datetime.datetime.utcnow() - min_event['created_at']).seconds

                    event_data = json.loads(min_event['data'])
                    if 'Event' in event_data:
                        collstats_min_event_info['name'] = event_data['Event']
                    else:
                        collstats_min_event_info['name'] = 'N/A'

                db_test_start = datetime.datetime.utcnow()
                active_events = self.mongo_db.events.count()
                db_test_duration = (
                    datetime.datetime.utcnow() - db_test_start).seconds

                if db_test_duration > 1:
                    db_error_message = "WARNING: DB is slow (%d seconds)" % db_test_duration

                if validate_db:
                    validation_info = self.mongo_db.validate_collection(
                        "events")

                if profile_db:
                    self.mongo_db.set_profiling_level(pymongo.ALL)
                    time.sleep(2)
                    #profile_info = self.mongo_db.profiling_info()
                    profile_info = self.mongo_db.system.profile.find_one()
                    self.mongo_db.set_profiling_level(pymongo.OFF)

                server_info = self.mongo_db_connection.server_info()

                db_online = True
                break

            except pymongo.errors.AutoReconnect:
                self.shared.logger.error(
                    "AutoReconnect caught from stats query")
                time.sleep(1)

            except Exception as ex:
                active_events = -1
                db_online = False
                db_error_message = str_utf8(ex)

                return json.dumps({
                                  "error": "DB error: %s" % (db_error_message)
                                  })

        return json.dumps({
                          "rse": {
                              "test_mode": self.test_mode,
                              "events": active_events,
                              "pp_stats": {
                                  "id_generator": {
                                      "attempts": self.shared.id_totalcnt,
                                      "retries": self.shared.id_retrycnt,
                                      "retry_rate": 0 if (self.shared.id_totalcnt == 0 or self.shared.id_retrycnt == 0) else float(self.shared.id_retrycnt) / self.shared.id_totalcnt
                                  }
                              }
                          },
                          "mongodb": {
                              "stats": {
                                  "background_flushing": {
                                      "last_finished": str(dbstats['backgroundFlushing']['last_finished']),
                                      "last_ms": dbstats['backgroundFlushing']['last_ms'],
                                      "flushes": dbstats['backgroundFlushing']['flushes'],
                                      "average_ms": dbstats['backgroundFlushing']['average_ms'],
                                      "total_ms": dbstats['backgroundFlushing']['total_ms']
                                  },
                                  "connections": {
                                      "current": dbstats['connections']['current'],
                                      "available": dbstats['connections']['available']
                                  },
                                  "uptime": dbstats['uptime'],
                                  "ok": dbstats['ok'],
                                  "network": {
                                      "num_requests": dbstats['network']['numRequests'],
                                      "bytes_out": dbstats['network']['bytesOut'],
                                      "bytes_in": dbstats['network']['bytesIn']
                                  },
                                  "opcounters": {
                                      "getmore": dbstats['opcounters']['getmore'],
                                      "insert": dbstats['opcounters']['insert'],
                                      "update": dbstats['opcounters']['update'],
                                      "command": dbstats['opcounters']['command'],
                                      "query": dbstats['opcounters']['query'],
                                      "delete": dbstats['opcounters']['delete']
                                  },
                                  "process": str(dbstats['process']),
                                  "asserts": {
                                      "msg": dbstats['asserts']['msg'],
                                      "rollovers": dbstats['asserts']['rollovers'],
                                      "regular": dbstats['asserts']['regular'],
                                      "warning": dbstats['asserts']['warning'],
                                      "user": dbstats['asserts']['user']
                                  },
                                  "uptime_estimate": dbstats['uptimeEstimate'],
                                  "mem": {
                                      "resident": dbstats['mem']['resident'],
                                      "supported": dbstats['mem']['supported'],
                                      "virtual": dbstats['mem']['virtual'],
                                      #"mappedWithJournal" : str(dbstats['mem']['mappedWithJournal']),
                                      "mapped": dbstats['mem']['mapped'],
                                      "bits": dbstats['mem']['bits']
                                  },
                                  "host": str(dbstats['host']),
                                  "version": dbstats['version'],
                                  "cursors": {
                                      "client_cursors_size": dbstats['cursors']['clientCursors_size'],
                                      "timed_out": dbstats['cursors']['timedOut'],
                                      "total_open": dbstats['cursors']['totalOpen']
                                  },
                                  "write_backs_queued": dbstats['writeBacksQueued'],
                                  "global_lock": {
                                      "total_time": dbstats['globalLock']['totalTime'],
                                      "current_queue": {
                                          "total": dbstats['globalLock']['currentQueue']['total'],
                                          "writers": dbstats['globalLock']['currentQueue']['writers'],
                                          "readers": dbstats['globalLock']['currentQueue']['readers']
                                      },
                                      "lockTime": dbstats['globalLock']['lockTime'],
                                      "ratio": (dbstats['globalLock']['lockTime'] / dbstats['globalLock']['totalTime']),
                                      "active_clients": {
                                          "total": dbstats['globalLock']['activeClients']['total'],
                                          "writers": dbstats['globalLock']['activeClients']['writers'],
                                          "readers": dbstats['globalLock']['activeClients']['readers']
                                      }
                                  },
                                  "local_time": str(dbstats['localTime'])
                              },
                              "coll_events_stats": {
                                  "count": collstats_events['count'],
                                  "ns": collstats_events['ns'],
                                  "ok": collstats_events['ok'],
                                  "last_extent_size": collstats_events['lastExtentSize'],
                                  "avg_obj_size": (0 if collstats_events['count'] == 0 else collstats_events['avgObjSize']),
                                  "total_index_size": collstats_events['totalIndexSize'],
                                  "userFlags": collstats_events['userFlags'],
                                  "systemFlags": collstats_events['systemFlags'],
                                  "num_extents": collstats_events['numExtents'],
                                  "nindexes": collstats_events['nindexes'],
                                  "storage_size": collstats_events['storageSize'],
                                  "padding_factor": collstats_events['paddingFactor'],
                                  "index_sizes": {
                                      "id": collstats_events['indexSizes']['_id_'],
                                      "get_events": collstats_events['indexSizes']['get_events']
                                  },
                                  "size": collstats_events['size'],
                                  "age_max": collstats_max_event_info,
                                  "age_min": collstats_min_event_info
                              },
                              "online": db_online,
                              "error": db_error_message,
                              "database": self.mongo_db.name,
                              "profiling":  {
                                  "reponse_length": str(profile_info['responseLength']) if profile_db else "N/A",
                                  "nreturned": str(profile_info['nreturned']) if profile_db else "N/A",
                                  "nscanned": str(profile_info['nscanned']) if profile_db else "N/A",
                              },
                              "collection": {
                                  "name": "events",
                                  "integrity": validation_info
                              },
                              "read_preference": self.mongo_db_connection.read_preference,
                              "safe": self.mongo_db_connection.safe,
                              "server_info": {
                                  "ok": server_info['ok'],
                                  "sys_info": server_info['sysInfo'],
                                  "version": server_info['version'],
                                  "version_array": server_info['versionArray'],
                                  "debug": server_info['debug'],
                                  "max_bson_object_size": server_info['maxBsonObjectSize'],
                                  "bits": server_info['bits']
                              }
                          }
                          })

    def get(self):
        if self.request.get_optional_param("verbose") == "true":
            self.response.write_header(
                "Content-Type", "application/json; charset=utf-8")
            self.response.write(
                self._create_report(
                    self.request.get_optional_param("profile_db") == "true",
                    self.request.get_optional_param("validate_db") == "true"))
        elif self._basic_health_check():
            self.response.write("OK\n")
        else:
            raise HttpError(503)

    def head(self):
        if self._basic_health_check():
            self.response.write("OK\n")
        else:
            raise HttpError(503)
