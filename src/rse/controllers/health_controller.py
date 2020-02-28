"""
@file health_controller.py
@author Kurt Griffiths, Xuan Yu, et al.

@brief
Health controller for Rackspace RSE Server.
"""

import time
import logging
from datetime import datetime
import hashlib
import json

import pymongo
from pymongo.errors import AutoReconnect
from tenacity import retry
from tenacity import stop_after_attempt as saa
from tenacity import wait_fixed as wait
from tenacity import retry_if_exception_type as extype

from .. import util
from ..rax.http import exceptions
from ..rax.http import rawr

log = logging.getLogger(__name__)


def format_datetime(dt):
    # @todo Move this into raxPy, put inside a namespace
    """Formats a datetime instance according to ISO 8601-Extended"""
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


class HealthController(rawr.Controller):
    """Provides web service health info"""
    """@todo Move this class into a separate file"""

    def __init__(self, mongo_db, shared, fields, authtoken_prefix, token_hashing_threshold):
        self.mongo_db = mongo_db  # MongoDB database for storing events
        # MongoDB connection for storing events
        self.mongo_db_connection = mongo_db.client
        # Test mode is supposed to relax auth requirements on verbose
        # healthcheck, but doesn't.
        self.test_mode = shared.test_mode
        self.shared = shared  # Shared performance counters, logging, etc.
        self.fields = fields
        self.authtoken_prefix = authtoken_prefix
        self.token_hashing_threshold = token_hashing_threshold

    def _event_range(self):
        events = {'first': pymongo.ASCENDING,
                  'last': pymongo.DESCENDING, }
        out = {}
        for evt, sortdir in list(events.items()):
            sorter = [('created_at', sortdir)]
            event = self.mongo_db.events.find_one(sort=sorter)
            if event:
                event['data'] = json.loads(event['data'])
                event['name'] = event['data'].get('Event', None)
                event['age'] = (datetime.utcnow() - event['created_at']).seconds
            out[evt] = event
        return out

    def _speedtest(self):
        db_test_start = datetime.utcnow()
        self.mongo_db.events.count()
        db_test_duration = (datetime.utcnow() - db_test_start).seconds
        return db_test_duration

    def _subreport_rse(self):
        return {
                "test_mode": self.test_mode,
                "events": self.mongo_db.events.count(),
                "pp_stats": {
                    "id_generator": {
                        "attempts": self.shared.id_totalcnt,
                        "retries": self.shared.id_retrycnt,
                        "retry_rate": self.shared.retry_rate,
                        }
                    }
                }

    def _subreport_mongo(self):
        return {
                "database": self.mongo_db.name,
                "server_info": self.mongo_db_connection.server_info(),
                "srvstats": self.mongo_db.command('serverStatus'),
                "evtstats": self.mongo_db.command({"collStats": "events"}),
                "event_range": self._event_range(),
                "readpref": self.mongo_db_connection.read_preference,
                "safe": self.mongo_db_connection.safe,
                }

    def _subreport_integrity(self):
        return self.mongo_db.validate_collection('events')

    def _subreport_profiling(self):
        self.mongo_db.set_profiling_level(pymongo.ALL)
        time.sleep(2)
        # profile_info = self.mongo_db.profiling_info()
        stats = self.mongo_db.system.profile.find()[0]
        self.mongo_db.set_profiling_level(pymongo.OFF)
        return stats

    @retry(stop=saa(10), wait=wait(0.5), retry=extype(AutoReconnect))
    def _basic_health_check(self):
        # Do something to exercise the db. Note that this must work on
        # secondaries (e.g. read-only slaves)
        self.mongo_db.events.count()
        return True

    @retry(stop=saa(10), wait=wait(0.5), retry=extype(AutoReconnect))
    def _full_report(self):
        # @todo Build up the report piecemeal so we can get partial results on
        # errors.
        # @todo Return a non-200 HTTP error code on error

        report = {}
        sub_reports = (
                ('rse', None, self._subreport_rse),
                ('mongo', None, self._subreport_mongo),
                ('versions', None, util.versions_report),
                ('profiling', 'profile_db', self._subreport_profiling),
                ('integrity', 'validate_db', self._subreport_integrity),
                )

        req = self.request
        for key, option, func in sub_reports:
            if option is None or req.get_optional_param(option) == "true":
                log.debug("Running report: %s", key)
                report[key] = dict(func())
            else:
                report[key] = "N/A. Pass %s=true to enable" % option

        report['warnings'] = []
        seconds = self._speedtest()
        if seconds > 1:
            msg = "WARNING: DB is slow (%d seconds)" % seconds
            report['warnings'].append(msg)

        report = util.filter_dataset(report, self.fields)
        return json.dumps(report, default=lambda o: str(o))

    def get(self):
        if self._prepare():
            self.response.write_header(
                "Content-Type", "application/json; charset=utf-8")
            if self.request.get_optional_param("verbose") == "true":
                self.response.write(self._full_report())
            elif self._basic_health_check():
                self.response.write("OK\n")
        else:
            log.warning("Health check failed.")
            raise exceptions.HttpError(503, 'Health check failed. Have a look on rse.log file.')

    def head(self):
        if self._basic_health_check():
            self.response.write("OK\n")
        else:
            log.warning("Health check failed.")
            raise exceptions.HttpError(503)

    def _format_key(self, auth_token):
        key = self.authtoken_prefix + auth_token

        if len(key) < self.token_hashing_threshold:
            return key

        sha = hashlib.sha512()
        sha.update((self.authtoken_prefix + auth_token).encode())
        hashed_token = sha.hexdigest().upper()

        # Converts hashed token to the format output by .NET's BitConverter
        # https://msdn.microsoft.com/en-us/library/3a733s97(v=vs.110).aspx
        return '-'.join(
            [
                ''.join(pair)
                for pair
                in zip(hashed_token[::2], hashed_token[1::2])
            ]
        )

    def _prepare(self):
        auth_token = self.request.get_optional_header('X-Auth-Token')
        if not auth_token:
            if self.test_mode:
                # Missing auth is OK in test mode
                log.warning(
                    "TEST MODE: Bypassing token validation."
                )
                return True
            else:
                # Auth token required in live mode
                log.error("Missing X-Auth-Token header (required in live mode).")
                return False
                # raise exceptions.HttpUnauthorized()

        # See if auth is cached by API
        try:
            if (
                    self.shared.authtoken_cache.get(
                        self._format_key(auth_token)
                    ) is None
            ):
                log.info('Unauthorized, Token is not cached by API into memcache.')
                return False
                #raise exceptions.HttpUnauthorized()

            else:
                return True

        except exceptions.HttpError:
            raise

        except Exception as ex:
            log.error(str(ex))
            raise exceptions.HttpServiceUnavailable()