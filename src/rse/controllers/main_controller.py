"""
@file main_controller.py
@author Kurt Griffiths, Xuan Yu, et al.

@brief
Main controller for Rackspace RSE Server
"""


import datetime
import hashlib
import time
import re
import random

import pymongo

# We got this off the web somewhere
from . import json_validator

from ..rax.http import exceptions
from ..rax.http import rawr


def str_utf8(instr):
    # @todo Move this into raxPy, give namespace
    return unicode(instr).encode("utf-8")


def format_datetime(dt):
    # @todo Move this into raxPy, put inside a namespace
    """Formats a datetime instance according to ISO 8601-Extended"""
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


class MainController(rawr.Controller):
    """Provides all RSE functionality"""

    def __init__(
        self,
        mongo_db,
        shared,
        authtoken_prefix,
        token_hashing_threshold,
        test_mode=False
    ):
        self.mongo_db = mongo_db  # MongoDB database for storing events
        self.authtoken_prefix = authtoken_prefix
        self.token_hashing_threshold = token_hashing_threshold
        self.test_mode = test_mode  # If true, relax auth/uuid requirements
        self.shared = shared  # Shared performance counters, logging, etc.

    def _format_key(self, auth_token):
        key = self.authtoken_prefix + auth_token

        if len(key) < self.token_hashing_threshold:
            return key

        sha = hashlib.sha512()
        sha.update(self.authtoken_prefix + auth_token)
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

    def prepare(self):
        auth_token = self.request.get_optional_header('X-Auth-Token')
        if not auth_token:
            if self.test_mode:
                # Missing auth is OK in test mode
                self.shared.logger.warning(
                    "TEST MODE: Bypassing token validation."
                )
                return
            else:
                # Auth token required in live mode
                self.shared.logger.error(
                    "Missing X-Auth-Token header (required in live mode)."
                )
                raise exceptions.HttpUnauthorized()

        # See if auth is cached by API
        try:
            if (
                self.shared.authtoken_cache.get(
                    self._format_key(auth_token)
                ) is None
            ):
                raise exceptions.HttpUnauthorized()

        except exceptions.HttpError:
            raise

        except Exception as ex:
            self.shared.logger.error(str_utf8(ex))
            raise exceptions.HttpServiceUnavailable()

    def _is_safe_user_agent(self, user_agent):
        """
        Quick heuristic to tell whether we can embed the given user_agent
        string in a JSON document
        """
        return not ('\\' in user_agent or '"' in user_agent)

    def _parse_client_uuid(self, user_agent):
        """Returns the UUID value of the specified User-Agent string"""
        try:
            # E.g., "550e8400-e29b-41d4-a716-446655440000" (see also
            # http://en.wikipedia.org/wiki/UUID)
            start_pos = user_agent.index("uuid/") + 5
            end_pos = start_pos + 36

            return user_agent[start_pos:end_pos]
        except:
            if self.test_mode:
                self.shared.logger.warning(
                    "TEST MODE: Bypassing User-Agent validation"
                )
                return "550e8400-dead-beef-dead-446655440000"
            else:
                raise exceptions.HttpBadRequest(
                    'Missing UUID in User-Agent header'
                )

    def _serialize_events(self, events):
        return (
            ""
            if not events
            else ",".join(
                [
                    (
                        '{"id":%d,"user_agent":"%s","created_at":"%s",'
                        '"age":%d,"data":%s}'
                    ) % (
                        event['_id'],
                        event['user_agent'],
                        format_datetime(
                            event['created_at']
                        ),
                        # Assumes nothing is older than a day
                        (
                            datetime.datetime.utcnow() - event['created_at']
                        ).seconds,
                        event['data']
                    ) for event in events
                ]
            )
        )

    def _debug_dump(self):
        sort_order = int(
            self.request.get_optional_param("sort", pymongo.ASCENDING))

        events = self.mongo_db.events.find(
            fields=['_id', 'user_agent', 'created_at', 'data', 'channel'],
            sort=[('_id', sort_order)])

        entries_serialized = self._serialize_events(events)
        self.response.write_header(
            "Content-Type", "application/json; charset=utf-8")
        self.response.write("[%s]" % str_utf8(entries_serialized))
        return

    def _explode_channel(self, channel):
        channels = [channel]

        marker_index = -1
        while True:
            marker_index = channel.rfind('/', 0, marker_index)
            if marker_index < 1:
                break

            channels.append(channel[0:marker_index])

        return channels

    def _calculate_next_id(self):
        event = self.mongo_db.events.find_one(
            fields=["_id"],
            sort=[("_id", -1)])

        if event:
            return event["_id"] + 1

        # If we get here, events is empty so fallback to our
        # side counter. We don't normally use it since this
        # approach is prone to race conditions. In this case
        # we likely won't get a race condition, since the server
        # cannot be very busy if the events collection was empty.
        return self.mongo_db.counters.find_one(
            {"_id": "last_known_id"}
        )["c"] + 1

    def _insert_event(self, channel_name, data, user_agent):
        """
        Since the agent is not stateless (remembers last_known_id), we must
        be careful to never insert one event with a larger ID, BEFORE inserting
        a different event with a smaller one. If that happens, then the agent
        could get the event with the larger ID first, and on the next query
        send last_known_id of that event which will cause us to miss the other
        event since that one has a smaller ID.

        Therefore, we can't use the usual method of keeping a side-counter
        and using it as the sole authority, like this:

            counter = self.mongo_db.counters.find_and_modify(
                {'_id': 'event_id'},
                {'$inc': {'c': 1}}
            )
        """

        # Retry until we get a unique _id (or die trying)
        event_insert_succeeded = False
        for retry_on_duplicate_key in xrange(100):
            # Increment stats counter
            self.shared.id_totalcnt += 1

            # @todo Move to a collision-tolerant ID pattern so that we
            # can scale out writes
            next_id = self._calculate_next_id()

            try:
                # Most of the time this will succeed, unless a different
                # instance beats us to the punch, in which case we'll just try
                # again
                self.mongo_db.events.insert(
                    {
                        "_id": next_id,
                        "data": data,
                        "channel": channel_name,
                        "user_agent": user_agent,
                        "uuid": self._parse_client_uuid(user_agent),
                        "created_at": datetime.datetime.utcnow()
                    },
                    safe=True
                )

                # Succeeded. Increment the side counter to keep it in sync with
                # next_id.
                self.mongo_db.counters.update(
                    {"_id": "last_known_id"}, {"$inc": {"c": 1}})

                # Our work is done here
                event_insert_succeeded = True
                break

            except pymongo.errors.DuplicateKeyError:
                self.shared.id_retrycnt += 1
                jitter = random.random() / 10  # Max 100 ms jitter
                backoff = retry_on_duplicate_key * 0.02  # Max 2 second sleep
                time.sleep(backoff + jitter)

            except pymongo.errors.AutoReconnect:
                self.shared.logger.error("AutoReconnect caught from insert")
                raise

        return event_insert_succeeded

    def _post(self, channel_name, data):
        """Handles a client submitting a new event (the data parameter)"""
        user_agent = self.request.get_header("User-Agent")

        # Verify that the data is valid JSON
        if not (
            json_validator.is_valid(data) and
            self._is_safe_user_agent(user_agent)
        ):
            raise exceptions.HttpBadRequest('Invalid JSON')

        # Insert the new event into the DB
        num_retries = 10  # 5 seconds
        for i in xrange(num_retries):
            try:
                if not self._insert_event(channel_name, data, user_agent):
                    raise exceptions.HttpServiceUnavailable()
                break

            except exceptions.HttpError as ex:
                self.shared.logger.error(str_utf8(ex))
                raise

            except pymongo.errors.AutoReconnect as ex:
                self.shared.logger.error(
                    "Retry %d of %d. Details: %s" % (
                        i,
                        num_retries,
                        str_utf8(ex)
                    )
                )

                if i == (num_retries - 1):  # Don't retry forever!
                    # Critical error (retrying probably won't help)
                    raise exceptions.HttpServiceUnavailable()
                else:
                    # Wait a moment for a new primary to be elected in case of
                    # failover
                    time.sleep(0.5)

        # If this is a JSON-P request, we need to return a response to the
        # callback
        callback_name = self.request.get_optional_param("callback")
        if callback_name:
            self.response.write_header("Content-Type", "text/javascript")

            # Security check
            if not self.shared.JSONP_CALLBACK_PATTERN.match(callback_name):
                raise exceptions.HttpBadRequest("Invalid callback name")

            self.response.write("%s({});" % callback_name)

        else:
            # POST succeeded, i.e., new event was created
            self.response.set_status(201)

    def _get_events(
        self,
        channel,
        last_known_id,
        uuid,
        sort_order,
        max_events
    ):
        # Get a list of events
        num_retries = 10
        for i in xrange(num_retries):
            try:
                events = self.mongo_db.events.find(
                    {'_id': {'$gt': last_known_id}, 'channel':
                     channel, 'uuid': {'$ne': uuid}},
                    fields=['_id', 'user_agent', 'created_at', 'data'],
                    sort=[('_id', sort_order)],
                    limit=max_events)

                break

            except pymongo.errors.AutoReconnect as ex:
                self.shared.logger.error(
                    "Retry %d of %d. Details: %s" % (
                        i,
                        num_retries,
                        str_utf8(ex)
                    )
                )

                if i == (num_retries - 1):  # Don't retry forever!
                    raise exceptions.HttpServiceUnavailable()
                else:
                    # Wait a moment for a new primary to be elected
                    time.sleep(0.5)

            except Exception as ex:
                self.shared.logger.error(str_utf8(ex))

                if i == num_retries - 1:  # Don't retry forever!
                    raise exceptions.HttpInternalServerError()

        return events

    def get(self):
        """
        Handles a "GET events" request for the specified channel (channel here
        includes the scope name)
        """
        channel_name = self.request.path

        if self.test_mode and channel_name == "/all":
            self._debug_dump()
            return

        # Note: case-sensitive for speed
        if self.request.get_optional_param("method") == "POST":
            self._post(channel_name, self.request.get_param("post-data"))
            return

        # Parse query params
        last_known_id = long(
            self.request.get_optional_param("last-known-id", 0))
        sort_order = int(
            self.request.get_optional_param("sort", pymongo.ASCENDING))
        max_events = min(
            500, int(self.request.get_optional_param("max-events", 200)))
        echo = (self.request.get_optional_param("echo") == "true")

        # Parse User-Agent string
        user_agent = self.request.get_header("User-Agent")
        uuid = ("e" if echo else self._parse_client_uuid(user_agent))

        # request parameter validation
        if sort_order not in (pymongo.ASCENDING, pymongo.DESCENDING):
            sort_order = pymongo.ASCENDING

        # Different values for "events" argument
        #    all - Get all events for both main and sub channels (@todo Lock
        #          this down for Retail Release)
        #    parent - Get anything that exactly matches the given sub channel,
        #             and each parent channel
        #    exact - Only get events that exactly match the given channel
        #            (default)
        filter_type = self.request.get_optional_param("events", "exact")
        events = []

        if filter_type == "parent":  # most common case first for speed

            # Note: We could do this in one query using a regex, but the regex
            # would not be in a format that allows the DB to use the get_events
            # index, so we split it up here. Note that this also sets us up for
            # sharding based on channel name.
            for each_channel in self._explode_channel(channel_name):
                events += self._get_events(
                    each_channel, last_known_id, uuid, sort_order, max_events)

            # Have to sort manually since we are combining the results of
            # several queries
            events.sort(key=lambda evt: evt['_id'], reverse=(
                sort_order == pymongo.DESCENDING))

        else:
            # @todo Remove this option so that we can shard based on channel
            # name.
            if filter_type == "all":
                channel_pattern = re.compile("^" + channel_name + "(/.+)?")

            else:  # force "exact"
                channel_pattern = channel_name

            events += self._get_events(
                channel_pattern, last_known_id, uuid, sort_order, max_events)

        # Write out the response
        entries_serialized = self._serialize_events(events)

        callback_name = self.request.get_optional_param("callback")
        if callback_name:
            # JSON-P
            self.response.write_header("Content-Type", "text/javascript")

            # Security check
            if not self.shared.JSONP_CALLBACK_PATTERN.match(callback_name):
                raise exceptions.HttpBadRequest('Invalid callback name')

            self.response.write("%s({\"channel\":\"%s\",\"events\":[%s]});" % (
                callback_name, channel_name, str_utf8(entries_serialized)))
        else:
            if not entries_serialized:
                self.response.set_status(204)
            else:
                self.response.write_header(
                    "Content-Type", "application/json; charset=utf-8")
                self.response.write("{\"channel\":\"%s\",\"events\":[%s]}" % (
                    channel_name, str_utf8(entries_serialized)))

    def post(self):
        """Handle a true HTTP POST event"""
        self._post(self.request.path, self.request.body)
