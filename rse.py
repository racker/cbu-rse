#!/usr/bin/env python

"""
@file rse.py
@author Kurt Griffiths
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

import rseutils
from httpex import *
import rawr

# Set up a specific logger with our desired output level
rse_logger = logging.getLogger()

# Initialize config paths
path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
local_config_path = os.path.join(dir_path, 'rse.conf')
global_config_path = '/etc/rse.conf'
default_config_path = os.path.join(dir_path, 'rse.default.conf')

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
    # @todo cache the authentication result for a few minutes
    
    auth_token = self.request.get_optional_header('X-Auth-Token');
    if not auth_token:
      if self.test_mode:
        # Missing auth is OK in test mode
        return
      else:
        # Auth token required in live mode
        logger.error("Missing X-Auth-Token header (required in live mode)")
        raise HttpUnauthorized()
      
    try:     
      headers = {
        'X-Agent-Key': self.reqest.get_header('X-Agent-Key'),
        'X-MachineName': self.reqest.get_header('X-MachineName'),
        'X-Architecture': self.reqest.get_header('X-Architecture'),
        'X-OperatingSystem': self.reqest.get_header('X-OperatingSystem'),
        'X-OperatingSystemVersion': self.reqest.get_header('X-OperatingSystemVersion'),
      }
      
      accountsvc = httplib.HTTPSConnection(self.accountsvc_host) if self.accountsvc_https else httplib.HTTPConnection(self.accountsvc_host) 
      accountsvc.request('GET', '/authentication/isauthenticated', None, headers)
      response = accountsvc.getresponse()
      
      if response.status != 200:
        logger.warning('Could not authorize request. Server returned HTTP %d. Unauthorized agent key: %s', response.status, agent_key)
        raise HttpUnauthorized()
        
    except Exception as ex:
      logger.error(ex)
      raise HttpUnauthorized()
    
  
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
      end_pos = start_pos + 36
      
      return user_agent[start_pos:end_pos]
    except:
      if self.test_mode:
        return "550e8400-dead-beef-dead-446655440000"
      else:
        raise HttpBadRequest('Missing UUID in User-Agent header')
  
  def _post(self, channel_name, data):
    """Handles a client submitting a new event (the data parameter)"""
    user_agent = self.request.get_header("User-Agent")
    
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise HttpBadRequest('Invalid JSON')
    
    # Insert the new event into the DB
    num_retries = 50
    for i in range(num_retries):
      try:
        # Keep retrying until we get a unique ID
        while True:
          self.mongo_db.events.insert({
            "_id": rseutils.time_id(),
            "data": data,
            "channel": channel_name,
            "user_agent": user_agent,
            "uuid": self._parse_client_uuid(user_agent),
            "created_at": datetime.datetime.utcnow()
          })
      
          last_error = self.mongo_db.error()
          if not last_error:
            # Success! Bail out!
            break
          elif last_error['code'] != 11000:
            # It is an error other than "duplicate ID", so don't try again!
            logger.error("Failed to insert event. MongoDB code: %d" % last_error['code'])
            raise HttpInternalServerError()
            
        # Success! No need to retry...
        break

      except pymongo.errors.AutoReconnect:
        if i == num_retries - 1: # Don't retry forever!
          raise
        else:
          time.sleep(2) # Wait a moment for a new primary to be elected

      except Exception as ex:
        # Critical error (retry probably won't help)
        logger.error(ex)
        raise ex
    
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
    """Handles a GET events request for the specified channel (channel here includes the scope name)"""

    channel_name = self.request.path

    # Note: case-sensitive for speed
    if self.request.get_optional_param("method") == "POST":
      self._post(channel_name, request.param("post-data"))
      return

    # Parse query params
    last_known_id = long(self.request.get_optional_param("last-known-id", 0))
    max_events = min(500, int(self.request.get_optional_param("max-events", 200)))
    echo = (self.request.get_optional_param("echo") == "true")
        
    # Get a list of events
    num_retries = 10
    for i in range(num_retries):
      try:
        user_agent = self.request.get_header("User-Agent")
        uuid = ("e" if echo else self._parse_client_uuid(user_agent))
        
        events = self.mongo_db.events.find(
          {'_id': {'$gt': last_known_id}, 'channel': channel_name, 'uuid': {'$ne': uuid}},
          fields=['_id', 'user_agent', 'created_at', 'data'],
          sort=[('_id', pymongo.ASCENDING)])
          
        break
      
      except pymongo.errors.AutoReconnect:
        if i == num_retries - 1:
          raise
        else:
          time.sleep(2) # Wait a moment for a new primary to be elected

    # http://www.skymind.com/~ocrow/python_string/
    entries_serialized = "" if not events else ",".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}'
      % (
      event['_id'],
      event['user_agent'],
      event['created_at'],
      event['data'])
      for event in events.limit(max_events)])
    
    # Write out the response
    callback_name = self.request.get_optional_param("callback")
    if callback_name:
      # JSON-P
      self.response.write_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.jsonp_callback_pattern.match(callback_name):
        raise HttpBadRequest('Invalid callback name')
      
      self.response.write("%s({\"channel\":\"%s\", \"events\":[%s]});" % (callback_name, channel_name, entries_serialized))
    else:
      if not entries_serialized:
        self.response.set_status(204)
      else:
        self.response.write_header("Content-Type", "application/json")
        self.response.write("{\"channel\":\"%s\", \"events\":[%s]}" % (channel_name, entries_serialized))
  
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
    rse_logger.setLevel(logging.DEBUG if config.get('rse', 'verbose') else logging.WARNING)
    handler = logging.handlers.RotatingFileHandler(config.get('rse', 'log-path'), maxBytes=1024*1024, backupCount=5)
    rse_logger.addHandler(handler)
  
    # Have one global connection to the DB across all handlers (pymongo manages its own connection pool)
    connection = pymongo.Connection(config.get('mongodb', 'host'), config.getint('mongodb', 'port'))
    mongo_db = connection[config.get('mongodb', 'database')]
    mongo_db.events.ensure_index([('uuid', pymongo.ASCENDING), ('channel', pymongo.ASCENDING)])
    
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

