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

auth_ttl_sec = 60

class HealthController(rawr.Controller):
  """Provides web service health info"""
  
  def get(self):
    self.response.write("Alive and kicking!\n")
    
class MainController(rawr.Controller):
  """Provides all RSE functionality"""
  
  # Speeds up member variable access
  __slots__ = ['accountsvc_host', 'accountsvc_https', 'mongo_db', 'test_mode', 'jsonp_callback_pattern']
  
  def __init__(self, accountsvc_host, accountsvc_https, mongo_db, test_mode = False):
    self.accountsvc_host = accountsvc_host # Account services host for authenticating requests
    self.accountsvc_https = accountsvc_https # Whether to use HTTPS for account services
    self.mongo_db = mongo_db # MongoDB connection for storing events
    self.jsonp_callback_pattern = re.compile("\A[a-zA-Z0-9_]+\Z") # Regex for validating JSONP callback name
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
      accountsvc.request('GET', '/v1.0/auth/isauthenticated', None, headers)
      response = accountsvc.getresponse()
    except Exception as ex:
      rse_logger.error(str(ex))
      raise HttpBadGateway()
      
    # Check whether the auth token was good
    if response.status != 200:
      rse_logger.warning('Could not authorize request. Server returned HTTP %d.', response.status)
      raise HttpUnauthorized() if (response.status / 100) == 4 else HttpBadGateway()
      
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
      fields=['_id', 'user_agent', 'created_at', 'data'],
      sort=[('_id', sort_order)])
      
    entries_serialized = "\"No events\"" if not events else ",\n".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      event['created_at'].strftime("%Y-%m-%d %H:%M:%SZ"),
      event['data'])
      for event in events])
      
    self.response.write_header("Content-Type", "application/json; charset=utf-8")
    self.response.write("[%s]" % entries_serialized)
    return

  def _post(self, channel_name, data):
    """Handles a client submitting a new event (the data parameter)"""
    user_agent = self.request.get_header("User-Agent")
        
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise HttpBadRequest('Invalid JSON')
        
    # Insert the new event into the DB
    num_retries = 30 # 30 seconds
    for i in range(num_retries):
      try:
        # Don't use this approach - a POST going to a different instance
        # may get the next counter, but end up inserting before we do (race 
        # condition). This could lead to a client getting the larger _id and
        # using it for last-known-id, effectively skipping the other event.
        #counter = self.mongo_db.counters.find_and_modify({'_id': 'event_id'}, {'$inc': {'c': 1}})
        
        while (True):
          last_id_record = self.mongo_db.events.find(
            fields=['_id'],
            sort=[('_id', pymongo.DESCENDING)],
            limit=1, slave_okay=False) # Get from master to reduce chance of race condition
        
          try:
            next_id = last_id_record.next()['_id'] + 1
          except:
            # No records found (basis case)
            next_id = 1
        
          # Most of the time this will succeed, unless a different instance
          # beat us to the bunch, in which case, we'll just try again
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
            
        # Success! No need to retry...
        break

      except Exception as ex:
        rse_logger.error(str(ex))
        
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
      if not self.jsonp_callback_pattern.match(callback_name):
        raise HttpBadRequest('Invalid callback name')
      
      self.response.write(callback_name)
      self.response.write('({"result":"OK"});')
  
  def get(self):
    """Handles a "GET events" request for the specified channel (channel here includes the scope name)"""

    channel_name = self.request.path
    
    if self.test_mode and channel_name == "/debug":
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
    #    all
    #    parent
    #    exact 
    eventsfilter = self.request.get_optional_param("events") 
    if eventsfilter == "all":
      channel_req = re.compile("^" + channel_name + "/.+")
    #elif eventsfilter == "parent":
    #elif eventsfilter == "exact":
    else:
      channel_req = channel_name
    
    # Get a list of events
    num_retries = 10
    for i in range(num_retries):
      try:
        user_agent = self.request.get_header("User-Agent")
        uuid = ("e" if echo else self._parse_client_uuid(user_agent))
        
        events = self.mongo_db.events.find(
          {'_id': {'$gt': last_known_id}, 'channel': channel_req, 'uuid': {'$ne': uuid}},
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
      '{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      event['created_at'].strftime("%Y-%m-%d %H:%M:%SZ"),
      event['data'])
      for event in events])

    # Write out the response
    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      # JSON-P
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.jsonp_callback_pattern.match(callback_name):
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
    connection = pymongo.Connection(config.get('mongodb', 'uri'))
    mongo_db = connection[config.get('mongodb', 'database')]
    
    # Initialize collections
    mongo_db.events.ensure_index([('uuid', pymongo.ASCENDING), ('channel', pymongo.ASCENDING)])
    if not mongo_db.counters.find_one({'_id': 'event_id'}):
      mongo_db.counters.insert({'_id': 'event_id', 'c': 0})
    
    accountsvc_host = config.get('account-services', 'host')
    accountsvc_https = config.getboolean('account-services', 'https')
    test_mode = config.getboolean('rse', 'test')
  
    # Setup routes
    self.add_route(r"/health$", HealthController),
    self.add_route(r"/.+", MainController, dict(accountsvc_host=accountsvc_host, accountsvc_https=accountsvc_https, mongo_db=mongo_db, test_mode=test_mode))

# WSGI app
app = RseApplication() 

# If running this script directly, startup a basic WSGI server for testing
if __name__ == "__main__":
  from wsgiref.simple_server import make_server

  httpd = make_server('', 8000, app)
  print "Serving on port 8000..."
  httpd.serve_forever()

