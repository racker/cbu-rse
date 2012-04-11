"""
@file main_controller.py
@author Kurt Griffiths, Xuan Yu, et al.

@brief
Main controller for Rackspace RSE Server
"""

import sys
import datetime
import time
import uuid
import re
import httplib

# Requires python 2.6 or better
import json

# These need to be installed (easy_install)
import pymongo

# We got this off the web somewhere - put in the same dir as rse.py
import json_validator

from rax.http.exceptions import *
from rax.http import rawr

from shared import *

# @todo Move this into raxPy, give namespace
def str_utf8(instr):
  return unicode(instr).encode("utf-8")          

# @todo Move this into raxPy, put inside a namespace
def format_datetime(dt):
  """Formats a datetime instance according to ISO 8601-Extended"""
  return dt.strftime("%Y-%m-%d %H:%M:%SZ");

    
class MainController(rawr.Controller):
  """Provides all RSE functionality"""
  
  def __init__(self, accountsvc_host, accountsvc_https, mongo_db, shared, test_mode = False):
    self.accountsvc_host = accountsvc_host # Account services host for authenticating requests
    self.accountsvc_https = accountsvc_https # Whether to use HTTPS for account services
    self.mongo_db = mongo_db # MongoDB database for storing events
    self.test_mode = test_mode # If true, relax auth/uuid requirements
    self.shared = shared # Shared performance counters, logging, etc.

  def prepare(self):
    auth_token = self.request.get_optional_header('X-Auth-Token');
    if not auth_token:
      if self.test_mode:
        # Missing auth is OK in test mode
        return
      else:
        # Auth token required in live mode
        self.shared.logger.error("Missing X-Auth-Token header (required in live mode)")
        raise HttpUnauthorized()
     
    # Cache hit rate algorithm: Since there's no time stamp, the total counter and the hit counter are truncated to half when the total counter 
    # reaches the integer maximum. This avoids BigInt arithmetic on 32-bit VMs. 
    # Note: Since 2^62-1 is large relative to the accumulation step, the scale remains reasonably accurate.
    if self.shared.cache_token_totalcnt >= (sys.maxint - 1):
      # Truncate to avoid overflow 
      self.shared.cache_token_totalcnt = self.shared.cache_token_totalcnt / 2
      self.shared.cache_token_hitcnt = self.shared.cache_token_hitcnt / 2
    
    self.shared.cache_token_totalcnt += 1

    # See if auth is cached
    if self.shared.authtoken_cache.is_cached(auth_token):
      # They are OK for the moment
      self.shared.cache_token_hitcnt += 1
      return
    
    # We don't have a record of this token, so proxy authentication to the Account Services API
    try:
      accountsvc = httplib.HTTPSConnection(self.accountsvc_host) if self.accountsvc_https else httplib.HTTPConnection(self.accountsvc_host) 
      accountsvc.request('GET', self.shared.AUTH_ENDPOINT, None, { 'X-Auth-Token': auth_token })
      response = accountsvc.getresponse()
    except Exception as ex:
      self.shared.logger.error(str_utf8(ex))
      raise HttpServiceUnavailable()
      
    # Check whether the auth token was good
    if response.status != 200:
      self.shared.logger.warning('Could not authorize request. Server returned HTTP %d for "%s".' % (response.status, auth_token))
      if (response.status / 100) == 4:
        raise HttpUnauthorized()
      else:
        raise HttpServiceUnavailable()
      
    try: 
      # Cache good token to reduce latency, and to reduce the load on Account Services
      self.shared.authtoken_cache.cache(auth_token)
    except Exception as ex: 
      self.shared.logger.error(str_utf8(ex))
      
  def _is_test_request(self):
    return False
    # @todo Enable this once we have new debug agent builds that use "live"
    #return self.request.get_optional_header('X-RSE-Mode') == 'test'          
  
  def _is_safe_user_agent(self, user_agent):
    """Quick heuristic to tell whether we can embed the given user_agent string in a JSON document"""
    for c in user_agent:
      if c == '\\' or c == '"':
        return False
    
    return True
  
  def _parse_client_uuid(self, user_agent):
    """Returns the UUID value of the specified User-Agent string"""
    try:
      # E.g., "550e8400-e29b-41d4-a716-446655440000" (see also http://en.wikipedia.org/wiki/UUID)
      start_pos = user_agent.index("uuid/") + 5
      end_pos =  start_pos + 36
      
      return user_agent[start_pos:end_pos]
    except:
      if self.test_mode:
        return "550e8400-dead-beef-dead-446655440000"
      else:
        raise HttpBadRequest('Missing UUID in User-Agent header')
  
  def _serialize_events(self, events):
    return "" if not events else ",".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","age":%d,"data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      format_datetime(event['created_at']),
      (datetime.datetime.utcnow() - event['created_at']).seconds, #<--- Assumes nothing is older than a day
      event['data'])
      for event in events])

  def _debug_dump(self):
    sort_order = long(self.request.get_optional_param("sort", pymongo.ASCENDING))

    # Get a reference to the correct collections, depending on mode
    events_collection = self.mongo_db.events
    if self._is_test_request():
      events_collection = self.mongo_db.events_test

    events = events_collection.find(
      fields=['_id', 'user_agent', 'created_at', 'data', 'channel'],
      sort=[('_id', sort_order)])
      
    entries_serialized = self._serialize_events(events)     
    self.response.write_header("Content-Type", "application/json; charset=utf-8")
    self.response.write("[%s]" % str_utf8(entries_serialized))
    return
    
  def _create_parent_pattern(self, channel):
    channel_fixed = channel.replace("/", "(/")[1:]
    channel_fixed += ")?" * channel_fixed.count("(")
    channel_fixed += "$"
    return re.compile("^" + channel_fixed)

  def _post(self, channel_name, data):
    """Handles a client submitting a new event (the data parameter)"""
    user_agent = self.request.get_header("User-Agent")
        
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise HttpBadRequest('Invalid JSON')

    # Get a reference to the correct collections, depending on mode
    # Note: Most likely scenario used as default               
    events = self.mongo_db.events
    counters = self.mongo_db.counters
    if self._is_test_request():
      events = self.mongo_db.events_test
      counters = self.mongo_db.counters_test

    # Insert the new event into the DB        
    num_retries = 30 # 30 seconds
    inserted_id = -1

    for i in range(num_retries):
      inserted_id = -1 # <--- Reset

      try:
        # Don't use this approach for normal ID creation.
        # A POST going to a different instance may get the next counter, but 
        # end up inserting before we do (race condition). This could lead to 
        # a client getting the larger _id and using it for last-known-id, 
        # effectively skipping the other event.
        # counter = self.mongo_db.counters.find_and_modify({'_id': 'event_id'}, {'$inc': {'c': 1}}) 

        # Grab the next ID - it's OK if two processes get the same, we will get an
        # exception when we try to insert a duplicate _id       
        inserted_id = counters.find_one({'_id': 'last_known_id'})['c']

        # Retry until we get a unique _id
        while (True):       
          # Most of the time this will succeed, unless a different instance
          # beat us to the punch, in which case, we'll just try again
          try:
            events.insert({
              "_id": inserted_id, 
              "data": data,
              "channel": channel_name,
              "user_agent": user_agent,
              "uuid": self._parse_client_uuid(user_agent),
              "created_at": datetime.datetime.utcnow()
            }, safe=True)
            
            # Don't retry with a different _id, since this one worked
            break
          except pymongo.errors.DuplicateKeyError:
            # Retry with a new value for _id. Since we normally count by
            # 10's, adding 1 or 2 in the case of another process having beat
            # us to the punch should succeed on the first retry.
            #
            # Note: We choose a random int to add jitter in the case that we 
            # have more 2 or more loosers that must retry, and we want them
            # to have a better chance of succeeding on their first try. This
            # is a hueristic since we have no way of knowing how many
            # processes are in contention
            #
            # @todo Tune based on load testing
            inserted_id += random.randint(1, 3) 
          except pymongo.errors.AutoReconnect:
            self.shared.logger.error("AutoReconnect caught from insert")
            raise

        # Success! No need to retry...
        break

      except HttpError as ex:
        self.shared.logger.error(str_utf8(ex)) 
        raise 
      except Exception as ex:
        self.shared.logger.error("Retry %d of %d. Details: %s" % (i, num_retries, str_utf8(ex))) 
        if i == (num_retries - 1): # Don't retry forever!
          # Critical error (retrying probably won't help)
          raise HttpInternalServerError()
        else:
          time.sleep(1) # Wait 1 second for a new primary to be elected

    # Sanity check
    if inserted_id == -1:
      self.shared.logger.error("inserted_id was never set")
      raise HttpInternalServerError()
    
    # Increment our side counter for the next POST
    # Note: 
    #   In the case of a race condition, where the current POST was the
    #   loser, this will result in, e.g., 10 => 30, and events having 
    #   _id's of [10, 11]. For 2 loosers, 10 => 40 and [10,11,12]. Should
    #   never overflow regardless, since max int in MongoDB is 2^63 - 1.
    counters.update({'_id': 'last_known_id'}, {'$inc': {'c': 10}})

    # If this is a JSON-P request, we need to return a response to the callback
    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      #self.response.write_header("Content-Type", "application/json-p")
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.shared.JSONP_CALLBACK_PATTERN.match(callback_name):
        raise HttpBadRequest('Invalid callback name')
      
      self.response.write(callback_name)
      self.response.write('({"result":"OK"});')
  
  def get(self):
    """Handles a "GET events" request for the specified channel (channel here includes the scope name)"""

    channel_name = self.request.path
    
    if self.test_mode and channel_name == "/all":
      self._debug_dump()
      return        

    # Note: case-sensitive for speed
    if self.request.get_optional_param("method") == "POST":
      self._post(channel_name, request.param("post-data"))
      return

    # Parse query params
    last_known_id = long(self.request.get_optional_param("last-known-id", 0))
    sort_order = long(self.request.get_optional_param("sort", pymongo.ASCENDING))
    max_events = min(500, int(self.request.get_optional_param("max-events", 200)))
    echo = (self.request.get_optional_param("echo") == "true")

    # Parse User-Agent string
    user_agent = self.request.get_header("User-Agent")
    uuid = ("e" if echo else self._parse_client_uuid(user_agent))

    # request parameter validation
    if sort_order not in (pymongo.ASCENDING, pymongo.DESCENDING):
      sort_order = pymongo.ASCENDING
    
    # Different values for "events" argument
    #    all - Get all events for both main and sub channels (@todo Lock this down for Retail Release)
    #    parent - Get anything that exactly matches the given sub channel, and each parent channel
    #    exact - Only get events that exactly match the given channel (default)
    filter_type = self.request.get_optional_param("events", "exact") 
    if filter_type == "parent": # most common case first for speed
      channel_pattern = self._create_parent_pattern(channel_name)
    elif filter_type == "all":
      channel_pattern = re.compile("^" + channel_name + "/.+")
    else: # force "exact"
      channel_pattern = channel_name
    
    # Get a reference to the correct collections, depending on mode
    # Note: Most likely scenario used as default to favor branch prediction              
    events_collection = self.mongo_db.events
    if self._is_test_request():
      events_collection = self.mongo_db.events_test

    # Get a list of events
    num_retries = 10
    for i in range(num_retries):
      try:        
        events = events_collection.find(
          {'_id': {'$gt': last_known_id}, 'channel': channel_pattern, 'uuid': {'$ne': uuid}},
          fields=['_id', 'user_agent', 'created_at', 'data'],
          sort=[('_id', sort_order)],
          limit=max_events)

        break
      
      except Exception as ex:
        self.shared.logger.error(str_utf8(ex))

        if i == num_retries - 1: # Don't retry forever!
          # Critical error (retrying probably won't help)
          raise HttpInternalServerError()
        else:
          time.sleep(1) # Wait a moment for a new primary to be elected

    # Write out the response
    entries_serialized = self._serialize_events(events)

    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      # JSON-P
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.shared.JSONP_CALLBACK_PATTERN.match(callback_name):
        raise HttpBadRequest('Invalid callback name')
      
      self.response.write("%s({\"channel\":\"%s\", \"events\":[%s]});" % (callback_name, channel_name, str_utf8(entries_serialized)))
    else:
      if not entries_serialized:
        self.response.set_status(204)
      else:
        self.response.write_header("Content-Type", "application/json; charset=utf-8")
        self.response.write("{\"channel\":\"%s\", \"events\":[%s]}" % (channel_name, str_utf8(entries_serialized)))
  
  def post(self):
    """Handle a true HTTP POST event"""
    self._post(self.request.path, self.request.body)
