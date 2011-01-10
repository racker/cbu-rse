#!/usr/bin/env python

"""
@file raxSvcRse.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
Rackspace RSE Server. Requires Python 2.x and the Tornado framework, as well as json_validator.py. Run with --help for command-line options.
"""

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
from tornado.options import define, options

# We got this off the web somewhere - put in the same dir as raxSvcRse.py
import json_validator

# Define command-line options, including defaults and help text
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
        
    # Initialize Tornado with our HTTP GET and POST event handlers
    tornado.web.Application.__init__(self, [
      (r"/([^&]+).*", MainHandler, dict(read_db=read_db, write_db=write_db))
    ])       
        
#todo: KPIs
#todo: Error logging for ops (with error buckets)
class MainHandler(tornado.web.RequestHandler):
  # Supposedly speeds up member variable access
  __slots__ = ['read_db', 'write_db', 'jsonp_callback_pattern']

  def initialize(self, read_db, write_db):
    self.read_db = read_db # Database for reads
    self.write_db = write_db # Database for writes
    self.jsonp_callback_pattern = re.compile("\A[a-zA-Z0-9_]+\Z") # Regex for validating JSONP callback name
      

  #todo: Authenticate the request
  #      -- Ask for private or session key from account server, based on public key - or, even better, say "sign this"
  def prepare(self):
    pass 

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
      
  def _want_jsonp(self):    
	  """Determines whether the client has requested a JSONP response"""
    try:
      mime_type = self.request.headers["Accept"]
      return mime_type == "application/json-p" or mime_type == "text/javascript"
    except:
      return False

  def _post(self, channel_name, data):
	  """Handles a client submitting a new event (the data parameter)"""
    user_agent = self._get_user_agent()        
    
    # Verify that the data is valid JSON
    if not (json_validator.is_valid(data) and self._is_safe_user_agent(user_agent)):
      raise tornado.web.HTTPError(400) 
        
    # Insert the new event into the DB    db_ok = False 
    for i in range(2):
    	try:
		    self.write_db.execute(
		      "INSERT INTO Events (data, channel, user_agent, user_agent_uuid, created_at)"
		      "VALUES (%s, %s, %s, %s, UTC_TIMESTAMP())"
		      ,
		      data, 
		      channel_name, 
		      user_agent, 
		      self._parse_client_uuid(user_agent))
		
		    break
		
		  except:
			  if i == 1:
				  raise
				else:
					self.write_db.reconnect() # Try to reconnect in case the problem was with our DB
         
  def get(self, channel_name):
	  """Handles a GET events request for the specified channel (channel here includes the scope name)"""

    # Note: case-sensitive for speed
    if self.get_argument("method", "GET") != "GET":
      self._post(channel_name, self.get_argument("post-data"))
      return       
    
    # Parse query params
    last_known_id = long(self.get_argument("last-known-id", 0))
    max_events = min(500, int(self.get_argument("max-events", 200)))
    echo = (self.get_argument("echo", "false") == "true")
     
    # Get a list of events
    for i in range(2):
	    try:
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
		
			break
			
		except:
			if i == 1:
				raise
			else:
				self.read_db.reconnect() # Try to reconnect in case the problem was with our DB
             
    # http://www.skymind.com/~ocrow/python_string/
    entries_serialized = "" if not events else ",".join([
      '{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}' 
      % (
      event.id, 
      event.user_agent, 
      event.created_at, 
      event.data) 
      for event in events])    
    
    # Write out the response
    if self._want_jsonp():
      #self.set_header("Content-Type", "application/json-p")
      self.set_header("Content-Type", "text/javascript")
      
      # Security check
      callback_name = self.request.headers["callback"]
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

