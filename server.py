#!/usr/bin/env python

import logging
import logging.handlers
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.database
import tornado.options
import tornado.web
import os.path
import uuid
import re

import json_validator
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

define("mysql_host_read", default="127.0.0.1:3306", help="event database host (read-only slave)")
define("mysql_host_write", default="127.0.0.1:3306", help="event database host (write master)")
define("mysql_database", default="pollcat", help="event database name")
define("mysql_user", default="pollcat", help="event database user")
define("mysql_password", default="one;crazy;kitty", help="event database password")
define("log_filename", default='/var/log/pollcat.log', help="log filename")
define("verbose", default='no', help="[yes|no] - determines logging level")

# Set up a specific logger with our desired output level
plc_logger = logging.getLogger()

class Application(tornado.web.Application):
  def __init__(self):              
    # Add the log message handler to the logger
    plc_logger.setLevel(logging.DEBUG if options.verbose == 'yes' else logging.WARNING)
    handler = logging.handlers.RotatingFileHandler(options.log_filename, maxBytes=1024*1024, backupCount=5)
    plc_logger.addHandler(handler)
  
    # Have one global connection to the DB across all handlers
    read_db = tornado.database.Connection(
      host=options.mysql_host_read, database=options.mysql_database,
      user=options.mysql_user, password=options.mysql_password)

    # Have one global connection to the DB across all handlers
    write_db = tornado.database.Connection(
      host=options.mysql_host_write, database=options.mysql_database,
      user=options.mysql_user, password=options.mysql_password)
        
    tornado.web.Application.__init__(self, [
      (r"/([^&]+).*", MainHandler, dict(read_db=read_db, write_db=write_db))
    ])       
        
#todo: KPIs
#todo: Error logging for ops (with error buckets)
class MainHandler(tornado.web.RequestHandler):
  # Supposedly speeds up member variable access
  __slots__ = ['read_db', 'write_db', 'jsonp_callback_pattern']

  def initialize(self, read_db, write_db):
    self.read_db = read_db
    self.write_db = write_db
    self.jsonp_callback_pattern = re.compile("\A[a-zA-Z0-9_]+\Z")
      

  #todo: Authenticate the request
  #      -- Pass login token or encrypted cookie (latter only for json-p requests) to auth servers
  #      -- Validate digest by looking up the user's key by user agent - key should be cached
  def prepare(self):
    pass 

  # quick heuristic to tell whether we can embed the given user_agent string in a JSON document
  def _is_safe_user_agent(self, user_agent):
    for c in user_agent:
      if c == '\\' or c == '"':
        return False
  
    return True            

  def _get_user_agent(self):
    return self.request.headers["User-Agent"]
  
  def _parse_client_uuid(self, user_agent):
    try:
      # E.g., "550e8400-e29b-41d4-a716-446655440000" (see also http://en.wikipedia.org/wiki/UUID)
      start_pos = user_agent.index("uuid/") + 5
      end_pos = start_pos + 36 
      
      return user_agent[start_pos:end_pos]             
    except:
      return "550e8400-dead-beef-dead-446655440000"
      #raise tornado.web.HTTPError(400)                
          
  def _want_jsonp(self):    
    try:
      mime_type = self.request.headers["Accept"]
      return mime_type == "application/json-p" or mime_type == "text/javascript"
    except:
      return False
          
  def _post(self, channel_name, data):
    user_agent = self._get_user_agent()        
    
    #Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise tornado.web.HTTPError(400) 
        
    self.write_db.execute(
      "INSERT INTO Events (data, channel, user_agent, user_agent_uuid, created_at)"
      "VALUES (%s, %s, %s, %s, UTC_TIMESTAMP())"
      ,
      data, 
      channel_name, 
      user_agent, 
      self._parse_client_uuid(user_agent))
          
  def get(self, channel_name):
    # Note: case-sensitive for speed
    if self.get_argument("method", "GET") != "GET":
      self._post(channel_name, self.get_argument("post-data"))
      return       
    
    last_known_id = long(self.get_argument("last-known-id", 0))
    max_events = min(500, int(self.get_argument("max-events", 100)))
    echo = (self.get_argument("echo", "false") == "true")
     
    events = self.read_db.query(
      "SELECT id, data, user_agent, created_at FROM Events"
      "  WHERE id > %s"
      "    AND channel = %s"            
      "    AND user_agent_uuid != %s"            
      "  ORDER BY id ASC"
      "  LIMIT %s"
      ,
      last_known_id,
      channel_name,
      ("e" if echo else self._parse_client_uuid(self._get_user_agent())),
      max_events)
             
    # http://www.skymind.com/~ocrow/python_string/
    entries_serialized = "" if not events else ",".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}' 
      % (
      event.id, 
      event.user_agent, 
      event.created_at, 
      event.data) 
      for event in events])    
    
    if self._want_jsonp():
      #self.set_header("Content-Type", "application/json-p")
      self.set_header("Content-Type", "text/javascript")
      
      # Security check
      callback_string = self.request.headers["callback"]
      if not self.jsonp_callback_pattern.match(callback_string):
        raise tornado.web.HTTPError(400)    
      
      self.write("%s([%s]);" % (callback_string, entries_serialized))
    else:
      self.set_header("Content-Type", "application/json")
      self.write("{\"channel\":\"/%s\", \"events\":[%s]}" % (channel_name, entries_serialized))
            
  def post(self, channel_name):
    self._post(channel_name, self.request.body)

def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()

