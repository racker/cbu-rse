#!/usr/bin/env python

import logging
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.database
import tornado.options
import tornado.web
import os.path
import uuid

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

define("mysql_host_read", default="127.0.0.1:3306", help="event database host (read-only slave)")
define("mysql_database", default="pollcat", help="event database name")
define("mysql_user", default="pollcat", help="event database user")
define("mysql_password", default="one;crazy;kitty", help="event database password")

class Application(tornado.web.Application):
    def __init__(self):              
        # Have one global connection to the DB across all handlers
        read_db = tornado.database.Connection(
            host=options.mysql_host_read, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)        
            
        tornado.web.Application.__init__(self, [
            (r"/(.+)", MainHandler, dict(read_db=read_db))
        ])       
        
#todo: KPIs
#todo: Error logging for ops (with error buckets)
class MainHandler(tornado.web.RequestHandler):
    # Supposedly speeds up member variable access
    __slots__ = ['read_db']

    def initialize(self, read_db):
        self.read_db = read_db  

    #todo: Authenticate the request
    #      -- Validate digest by looking up the user's key by user agent (only allow internal user agents for this service)
    #      -- Possibly put bridge.py on a box that is firewalled off from the internet altogether
    def prepare(self):
        pass     

    def _get_user_agent(self):
        try:
            return self.request.headers["User-Agent"]
        except:
            return "test/1.0 uuid/550e8400-e29b-41d4-a716-446655440000"
    
    def _parse_client_uuid(self, user_agent):
        try:
            # E.g., "550e8400-e29b-41d4-a716-446655440000" (see also http://en.wikipedia.org/wiki/UUID)
            start_pos = user_agent.index("uuid/") + 5
            end_pos = start_pos + 36 
            
            return user_agent[pos:end_pos]             
        except:
            return "550e8400-e29b-41d4-a716-446655440000"
            #raise tornado.web.HTTPError(400)                          
   
    def get(self, channel_name):       
        last_known_id = long(self.get_argument("last-known-id", 0))
        max_events = min(5000, int(self.get_argument("max-events", 1000)))
        echo = self.get_argument("echo", "false")        
        
        sql = (
            "SELECT id, data, user_agent, created_at FROM Events"
            "  WHERE id > %s")
        
        if self.get_argument("mode", "prefix") == "prefix":
            sql += "    AND channel like %s"            
            channel_name += "%"
        else:
            sql += "    AND channel = %s"            
        
        sql += ( 
            "    AND user_agent_uuid != %s"            
            "  ORDER BY id ASC"
            "  LIMIT %s")    
         
        events = self.read_db.query(
            sql
            ,
            last_known_id,
            channel_name,
            ("echo" if echo else self._parse_client_uuid(self._get_user_agent())),
            max_events)
            
        # http://www.skymind.com/~ocrow/python_string/    
        entries_serialized = "" if not events else ",".join([
            '{{"id":%d,"user_agent":"%s","created_at":"%s","data":%s}}' 
            % (
            event.id, 
            event.user_agent, 
            event.created_at, 
            event.data) 
            for event in events])    
        
        self.set_header("Content-Type", "application/json")
        self.write("[%s]" % entries_serialized)

def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
