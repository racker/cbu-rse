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
import datetime
import time
import logging
import logging.handlers
import os.path
import uuid
import re
import ConfigParser
import io
import httplib

# Requires python 2.6 or better
import json

# These need to be installed (easy_install)
import pymongo
import argparse

# We got this off the web somewhere - put in the same dir as raxSvcRse.py
import json_validator

from rax.http.exceptions import *
from rax.http import rawr

# Set up a specific logger with our desired output level
rse_logger = logging.getLogger(__name__)

# Initialize config paths
path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
local_config_path = os.path.join(dir_path, 'rse.conf')
global_config_path = '/etc/rse.conf'
default_config_path = os.path.join(dir_path, 'rse.default.conf')
auth_endpoint = '/v1.0/auth/isauthenticated'
auth_health_endpoint = '/v1.0/help/developerguide'
jsonp_callback_pattern = re.compile("\A[a-zA-Z0-9_]+\Z") # Regex for validating JSONP callback name
auth_ttl_sec = 90

health_auth_headers = {
  'X-Auth-Token': 'HealthCheck'
}

class HealthController(rawr.Controller):
  """Provides web service health info"""

  def __init__(self, accountsvc_host, accountsvc_https, mongo_db, test_mode):
    self.accountsvc_host = accountsvc_host # Account services host for authenticating requests
    self.accountsvc_https = accountsvc_https # Whether to use HTTPS for account services
    self.mongo_db = mongo_db # MongoDB database for storing events
    self.mongo_db_connection = mongo_db.connection # MongoDB connection for storing events
    self.test_mode = test_mode # If true, relax auth/uuid requirements

  def _basic_health_check(self):
    # Check our auth endpoint    
    try:
      accountsvc = httplib.HTTPSConnection(self.accountsvc_host, timeout=2) if self.accountsvc_https else httplib.HTTPConnection(self.accountsvc_host, timeout=2) 
      accountsvc.request('GET', auth_health_endpoint, None, health_auth_headers)
      auth_response = accountsvc.getresponse()
      if auth_response.status != 200:
        return False
    except Exception as ex:
      return False
    
    try:
      self.mongo_db.events.count()
    except Exception as ex:
      return False
    
    return True

  def _create_report(self, profile_db, validate_db):
    # Check our auth endpoint
   
    auth_error_message = "N/A"
    auth_online = False
    try:
      auth_test_start = datetime.datetime.utcnow()

      accountsvc = httplib.HTTPSConnection(self.accountsvc_host) if self.accountsvc_https else httplib.HTTPConnection(self.accountsvc_host) 
      accountsvc.request('GET', auth_endpoint, None, health_auth_headers)
      auth_response = accountsvc.getresponse()

      if auth_response.status == 401:
        auth_online = True

        auth_test_duration = (datetime.datetime.utcnow() - auth_test_start).seconds          
        if auth_test_duration > 2:
          auth_error_message = "WARNING: Auth endpoint is slow (%d seconds)" % auth_test_duration
      else:
        auth_error_message = "Auth endpoint returned HTTP %d instead of HTTP 401" % auth_response.status
    except Exception as ex:
      auth_error_message = str(ex)          
    
    validation_info = "N/A. Pass validate_db=true to enable."
    profile_info = "N/A. Pass profile_db=true to enable."
    db_error_message = "N/A"
    try:
      db_test_start = datetime.datetime.utcnow()
      active_events = self.mongo_db.events.count()
      db_test_duration = (datetime.datetime.utcnow() - db_test_start).seconds          

      db_online = True
      if db_test_duration > 1:
          db_error_message = "WARNING: DB is slow (%d seconds)" % db_test_duration
          
      if validate_db:
        validation_info = self.mongo_db.validate_collection("events")

      if profile_db:
        self.mongo_db.set_profiling_level(pymongo.ALL)
        time.sleep(2)
        profile_info = self.mongo_db.profiling_info()
        self.mongo_db.set_profiling_level(pymongo.OFF)

    except Exception as ex:
      active_events = -1
      db_online = False
      db_error_message = str(ex)     
  
    return json.dumps({
      "rse": {
        "test_mode": self.test_mode,
        "events": active_events
      },
      "auth": {
        "url": "%s://%s%s" % ("https" if self.accountsvc_https else "http", self.accountsvc_host, auth_endpoint),        
        "online": auth_online,
        "error": auth_error_message,
        "ttl": auth_ttl_sec
      },
      "mongodb": {
        "host": self.mongo_db_connection.host,
        "port": self.mongo_db_connection.port,
        "nodes": [n for n in self.mongo_db_connection.nodes],
        "online": db_online,
        "error": db_error_message,
        "database": self.mongo_db.name,
        "collection": {
          "name": "events",
          "integrity": validation_info
          #"profiling": profile_info
        },
        "slave_okay": self.mongo_db_connection.slave_okay,
        "safe": self.mongo_db_connection.safe,
        "server_info": self.mongo_db_connection.server_info()
      }
    })
  
  def get(self):
    if self.request.get_optional_param("verbose") == "true":
      self.response.write_header("Content-Type", "application/json; charset=utf-8")
      self.response.write(
        self._create_report(
          self.request.get_optional_param("profile_db") == "true",
          self.request.get_optional_param("validate_db") == "true"))
    elif self._basic_health_check():
      self.response.write("OK\n")
    else:
      raise HttpError(503)    
    
class MainController(rawr.Controller):
  """Provides all RSE functionality"""
  
  # Speeds up member variable access
  __slots__ = ['accountsvc_host', 'accountsvc_https', 'mongo_db', 'test_mode']
  
  def __init__(self, accountsvc_host, accountsvc_https, mongo_db, test_mode = False):
    self.accountsvc_host = accountsvc_host # Account services host for authenticating requests
    self.accountsvc_https = accountsvc_https # Whether to use HTTPS for account services
    self.mongo_db = mongo_db # MongoDB database for storing events
    self.test_mode = test_mode # If true, relax auth/uuid requirements
  
  def prepare(self):
    auth_token = self.request.get_optional_header('X-Auth-Token');
    if not auth_token:
      if self.test_mode:
        # Missing auth is OK in test mode
        return
      else:
        # Auth token required in live mode
        rse_logger.error("Missing X-Auth-Token header (required in live mode)")
        raise HttpUnauthorized()
     
    # Read X-* headers
    try:     
      # Check for non-expired, cached authentication
      auth_record = self.mongo_db.authcache.find_one(
        {'auth_token': auth_token, 'expires': {'$gt': time.time()}})
     
    except Exception as ex:
      # Oh well. Log the error and proceed as if no cached authentication
      rse_logger.error(str(ex))

    if auth_record:
      # They are OK for the moment
      return
    
    headers = {
      'X-Auth-Token': auth_token
    }

    # Proxy authentication to the Account Services API
    try:
      accountsvc = httplib.HTTPSConnection(self.accountsvc_host) if self.accountsvc_https else httplib.HTTPConnection(self.accountsvc_host) 
      accountsvc.request('GET', auth_endpoint, None, headers)
      response = accountsvc.getresponse()
    except Exception as ex:
      rse_logger.error(str(ex))
      raise HttpBadGateway()
      
    # Check whether the auth token was good
    if response.status != 200:
      rse_logger.warning('Could not authorize request. Server returned HTTP %d for "%s".' % (response.status, auth_token))
      if (response.status / 100) == 4:
        raise HttpUnauthorized()
      else:
        raise HttpBadGateway()
      
    # Cache good token to increase performance and reduce the load on Account Services
    self.mongo_db.authcache.insert(
        {'auth_token': auth_token, 'expires': time.time() + auth_ttl_sec})
           
  
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
  
  def _debug_dump(self):

    sort_order = long(self.request.get_optional_param("sort", pymongo.ASCENDING))

    events = self.mongo_db.events.find(
      fields=['_id', 'user_agent', 'created_at', 'data', 'channel'],
      sort=[('_id', sort_order)])
      
    entries_serialized = "\"No events\"" if not events else ",\n".join([
      '{"id":%d,"user_agent":"%s","channel":"%s","created_at":"%s","age":%d,"data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      event['channel'],
      event['created_at'].strftime("%Y-%m-%d %H:%M:%SZ"),
      (datetime.datetime.utcnow() - event['created_at']).seconds, #<--- Assumes nothing is older than a day
      event['data'])
      for event in events])
      
    self.response.write_header("Content-Type", "application/json; charset=utf-8")
    self.response.write("[%s]" % str(entries_serialized))
    return
    
  def _create_parent_pattern(self, channel):
    channel_fixed = channel.replace("/", "(/")[1:]
    channel_fixed += ")?" * channel_fixed.count("(")
    return re.compile(channel_fixed)

  def _post(self, channel_name, data):
    """Handles a client submitting a new event (the data parameter)"""
    user_agent = self.request.get_header("User-Agent")
        
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise HttpBadRequest('Invalid JSON')
        
    # Increment our fallback counter (don't use normally, because it's prone to race conditions)
    self.mongo_db.counters.update({'_id': 'last_known_id'}, {'$inc': {'c': 1}})
        
    # Insert the new event into the DB        
    num_retries = 30 # 30 seconds
    for i in range(num_retries):
      try:
        # Don't use this approach for normal ID creation.
        # A POST going to a different instance may get the next counter, but 
        # end up inserting before we do (race condition). This could lead to 
        # a client getting the larger _id and using it for last-known-id, 
        # effectively skipping the other event.
        # counter = self.mongo_db.counters.find_and_modify({'_id': 'event_id'}, {'$inc': {'c': 1}})
        
        while (True):
          last_id_record = self.mongo_db.events.find_one(
            fields=['_id'],
            sort=[('_id', pymongo.DESCENDING)],
            limit=1)
        
          try:
            next_id = last_id_record['_id'] + 1
          except:
            # No records found (basis case)
            rse_logger.warning("No events. Falling back to global counter.")
            next_id = self.mongo_db.counters.find_one({'_id': 'last_known_id'})['c']
        
          # Most of the time this will succeed, unless a different instance
          # beat us to the punch, in which case, we'll just try again
          try:
            self.mongo_db.events.insert({
              "_id": next_id, 
              "data": data,
              "channel": channel_name,
              "user_agent": user_agent,
              "uuid": self._parse_client_uuid(user_agent),
              "created_at": datetime.datetime.utcnow()
            }, safe=True)
            
            # Don't retry
            break
          except pymongo.errors.DuplicateKeyError:
            # Retry
            pass
          except pymongo.errors.AutoReconnect:
            rse_logger.error("AutoReconnect caught from insert")
            raise
            
        # Success! No need to retry...
        break

      except Exception as ex:
        rse_logger.error(str(ex))
        rse_logger.error("Retry %d of %d. Details: %s" % (i, num_retries, str(ex))) 
        if i == num_retries - 1: # Don't retry forever!
          # Critical error (retrying probably won't help)
          raise HttpInternalServerError()
        else:
          time.sleep(1) # Wait 1 second for a new primary to be elected
    
    # If this is a JSON-P request, we need to return a response to the callback
    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      #self.response.write_header("Content-Type", "application/json-p")
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not jsonp_callback_pattern.match(callback_name):
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
    
    # Get a list of events
    num_retries = 10
    for i in range(num_retries):
      try:
        user_agent = self.request.get_header("User-Agent")
        uuid = ("e" if echo else self._parse_client_uuid(user_agent))
        
        events = self.mongo_db.events.find(
          {'_id': {'$gt': last_known_id}, 'channel': channel_pattern, 'uuid': {'$ne': uuid}},
          fields=['_id', 'user_agent', 'created_at', 'data'],
          sort=[('_id', sort_order)],

          limit=max_events)
        break
      
      except Exception as ex:
        rse_logger.error(str(ex))

        if i == num_retries - 1: # Don't retry forever!
          # Critical error (retrying probably won't help)
          raise HttpInternalServerError()
        else:
          time.sleep(1) # Wait a moment for a new primary to be elected

    # http://www.skymind.com/~ocrow/python_string/
    entries_serialized = "" if not events else ",".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","age":%d,"data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      event['created_at'].strftime("%Y-%m-%d %H:%M:%SZ"),
      (datetime.datetime.utcnow() - event['created_at']).seconds, #<--- Assumes nothing is older than a day
      event['data'])
      for event in events])

    # Write out the response
    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      # JSON-P
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not jsonp_callback_pattern.match(callback_name):
        raise HttpBadRequest('Invalid callback name')
      
      self.response.write("%s({\"channel\":\"%s\", \"events\":[%s]});" % (callback_name, channel_name, str(entries_serialized)))
    else:
      if not entries_serialized:
        self.response.set_status(204)
      else:
        self.response.write_header("Content-Type", "application/json; charset=utf-8")
        self.response.write("{\"channel\":\"%s\", \"events\":[%s]}" % (channel_name, str(entries_serialized)))
  
  def post(self):
    """Handle a true HTTP POST event"""
    self._post(self.request.path, self.request.body)


class RseApplication(rawr.Rawr):
  """RSE app for encapsulating initialization"""
  
  def __init__(self): 
    rawr.Rawr.__init__(self)
    
    # Parse options
    config = ConfigParser.ConfigParser()
    config.read(default_config_path)
    
    if os.path.exists(local_config_path):
       config.read(local_config_path)
    elif os.path.exists(global_config_path):
       config.read(global_config_path)

    # Add the log message handler to the logger
    rse_logger.setLevel(logging.DEBUG if config.get('logging', 'verbose') else logging.WARNING)
    
    formatter = logging.Formatter('%(asctime)s - RSE - PID %(process)d - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s')
   
    if config.getboolean('logging', 'filelog'):
      handler = logging.handlers.RotatingFileHandler(config.get('logging', 'filelog-path'), maxBytes=5 * 1024*1024, backupCount=5)    
      handler.setFormatter(formatter);
      rse_logger.addHandler(handler)
    
    if config.getboolean('logging', 'syslog'):
      handler = logging.handlers.SysLogHandler(address=config.get('logging', 'syslog-address'))    
      handler.setFormatter(formatter);
      rse_logger.addHandler(handler)
    
    # Have one global connection to the DB across all handlers (pymongo manages its own connection pool)
    # WARNING: Even if you set slaveok in the URI, you must also set the param in the Connection constructor
    connection = pymongo.Connection(config.get('mongodb', 'uri'), slaveok=True)
    mongo_db = connection[config.get('mongodb', 'database')]
    
    # Initialize collections
    for i in range(10):
      try:
        mongo_db.events.ensure_index([('uuid', pymongo.ASCENDING), ('channel', pymongo.ASCENDING)])
        break
      except pymongo.errors.AutoReconnect:
        time.sleep(1)

    # Only used for fallback if we don't have any events to use for the ID
    # WARNING: Counter must start at a value greater than 0 per the RSE spec!
    if not mongo_db.counters.find_one({'_id': 'last_known_id'}):
      mongo_db.counters.insert({'_id': 'last_known_id', 'c': 1})
    
    accountsvc_host = config.get('account-services', 'host')
    accountsvc_https = config.getboolean('account-services', 'https')
    test_mode = config.getboolean('rse', 'test')
  
    # Setup routes
    options = dict(accountsvc_host=accountsvc_host, accountsvc_https=accountsvc_https, mongo_db=mongo_db, test_mode=test_mode)
    self.add_route(r"/health$", HealthController, options)
    self.add_route(r"/.+", MainController, options)

# WSGI app
app = RseApplication() 

# If running this script directly, startup a basic WSGI server for testing
if __name__ == "__main__":
  from wsgiref.simple_server import make_server

  httpd = make_server('', 8000, app)
  print "Serving on port 8000..."
  httpd.serve_forever()

