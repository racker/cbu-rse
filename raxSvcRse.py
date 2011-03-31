#!/usr/bin/env python

"""
@file raxSvcRse.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
Rackspace RSE Server. Requires Python 2.x and the Tornado framework, as well as json_validator.py. Run with --help for command-line options.

@pre
Servers have syncronized clocks (ntpd).
Python 2.x is installed.
Tornado framework and pymongo also installed.
ulimit -n 2048 # or better
sysctl -w net.core.somaxconn="2048" # or better
"""

import datetime
import time
import pymongo
import logging
import logging.handlers
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os.path
import uuid
import re
from tornado.options import define, options

# We got this off the web somewhere - put in the same dir as raxSvcRse.py
import json_validator

# Define command-line options, including defaults and help text
define("port", default=8888, help="run on the given port", type=int)

define("mongodb_host", default="127.0.0.1", help="event mongod/mongos host")
define("mongodb_port", default=27017, help="event mongod/mongos port", type=int)
define("mongodb_database", default='rse', help="event mongod/mongos port")

define("log_filename", default='/var/log/rse.log', help="log filename")
define("verbose", default='no', help="[yes|no] - determines logging level")

# Set up a specific logger with our desired output level
rse_logger = logging.getLogger()

class Application(tornado.web.Application):
  def __init__(self):
    # Add the log message handler to the logger
    rse_logger.setLevel(logging.DEBUG if options.verbose == 'yes' else logging.WARNING)
    handler = logging.handlers.RotatingFileHandler(options.log_filename, maxBytes=1024*1024, backupCount=5)
    rse_logger.addHandler(handler)
    
    # Have one global connection to the DB across all handlers (pymongo manages its own connection pool)
    connection = pymongo.Connection(options.mongodb_host, options.mongodb_port)
    mongo_db = connection[options.mongodb_database]
    mongo_db.events.ensure_index([('uuid', pymongo.ASCENDING), ('channel', pymongo.ASCENDING)])
    #Shard based on the above (?)
    
    # Initialize Tornado with our HTTP GET and POST event handlers
    tornado.web.Application.__init__(self, [
      (r"/([^&]+).*", MainHandler, dict(mongo_db=mongo_db))
    ])

#todo: Deal with large objects? Graceful error?
#todo: Enable/test sharding + replica sets (each pair should reside on different physical boxes, can double up with masters)
#todo: KPIs
#todo: Error logging for ops (with error buckets)
class MainHandler(tornado.web.RequestHandler):
  # Supposedly speeds up member variable access
  __slots__ = ['mongo_db', 'jsonp_callback_pattern']
  
  def initialize(self, mongo_db):
    self.mongo_db = mongo_db # MongoDB connection for storing events
    self.jsonp_callback_pattern = re.compile("\A[a-zA-Z0-9_]+\Z") # Regex for validating JSONP callback name
  
  #todo: Authenticate the request
  #      -- Ask for private or session key from account server, based on public key - or, even better, say "sign this"
  #def prepare(self):
  #  cache the authentication for 5 minutes (memcache?)
  #  pass
  
  def _is_safe_user_agent(self, user_agent):
    """Quick heuristic to tell whether we can embed the given user_agent string in a JSON document"""
    for c in user_agent:
      if c == '\\' or c == '"':
        return False
    
    return True
  
  def _get_user_agent(self):
    """Returns the User-Agent header"""
    return self.request.headers["User-Agent"]
  
  def _parse_client_uuid(self, user_agent):
    """Returns the UUID value of the specified User-Agent string"""
    try:
      # E.g., "550e8400-e29b-41d4-a716-446655440000" (see also http://en.wikipedia.org/wiki/UUID)
      start_pos = user_agent.index("uuid/") + 5
      end_pos = start_pos + 36
      
      return user_agent[start_pos:end_pos]
    except:
      return "550e8400-dead-beef-dead-446655440000"
      #raise tornado.web.HTTPError(400)
  
  def _post(self, channel_name, data):
    """Handles a client submitting a new event (the data parameter)"""
    user_agent = self._get_user_agent()
    
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise tornado.web.HTTPError(400)
    
    # Insert the new event into the DB
    num_retries = 10
    for i in range(num_retries):
      try:
        # Keep retrying until we get a unique ID
        while True:
          self.mongo_db.events.insert({
            "_id": time.time(),
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
            raise tonado.web.HTTPError(500)
            
        # Success! No need to retry...
        break

      except pymongo.errors.AutoReconnect:
        if i == num_retries - 1: # Don't retry forever!
          raise
        else:
          time.sleep(2) # Wait a moment for a new primary to be elected

      except:
        # Critical error (retry probably won't help)
        raise
    
    callback_name = self.get_argument("callback", "")
    if callback_name:
      #self.set_header("Content-Type", "application/json-p")
      self.set_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.jsonp_callback_pattern.match(callback_name):
        raise tornado.web.HTTPError(400)
      
      self.write(callback_name + "({\"result\":\"OK\"});")
  
  def get(self, channel_name):
    """Handles a GET events request for the specified channel (channel here includes the scope name)"""
    
    # Note: case-sensitive for speed
    if self.get_argument("method", None) == "POST":
      self._post(channel_name, self.get_argument("post-data"))
      return

    # Parse query params
    last_known_id = long(self.get_argument("last-known-id", 0))
    max_events = min(500, int(self.get_argument("max-events", 200)))
    echo = (self.get_argument("echo", "false") == "true")
        
    # Get a list of events
    num_retries = 10
    for i in range(num_retries):
      try:
        uuid = ("e" if echo else self._parse_client_uuid(self._get_user_agent()))
        
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
    callback_name = self.get_argument("callback", "")
    if callback_name:
      #self.set_header("Content-Type", "application/json-p")
      self.set_header("Content-Type", "text/javascript")
      
      # Security check
      if not self.jsonp_callback_pattern.match(callback_name):
        raise tornado.web.HTTPError(400)
      
      self.write("%s({\"channel\":\"/%s\", \"events\":[%s]});" % (callback_name, channel_name, entries_serialized))
    else:
      self.set_header("Content-Type", "application/json")
      self.write("{\"channel\":\"/%s\", \"events\":[%s]}" % (channel_name, entries_serialized))
  
  def post(self, channel_name):
    """Handle a true HTTP POST event"""
    self._post(channel_name, self.request.body)

def main():
  tornado.options.parse_command_line()
  http_server = tornado.httpserver.HTTPServer(Application())
  http_server.listen(options.port)
  tornado.ioloop.IOLoop.instance().start()

# If running this script directly, execute the "main" routine
if __name__ == "__main__":
  main()

