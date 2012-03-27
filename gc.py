#!/usr/bin/env python

"""
@file gc.py
@author Kurt Griffiths
$Author$  <=== populated-by-subversion
$Revision$  <=== populated-by-subversion
$Date$  <=== populated-by-subversion

@brief
RSE garbage collector. Requires Python 2.7 or better, argparse, and pymongo

@todo
Should this share configuration with RseApplication?
"""

import pymongo
import argparse
import time
import datetime

def remove_expired_events(host, port, db_name, ttl_sec):
  """Removes events from the specified database that have expired based on ttl_sec"""
  
  connection = pymongo.Connection(host, port)
  db = connection[db_name]
  
  # Create a date line to figure out the maximum event age
  max_age = datetime.datetime.utcnow() - datetime.timedelta(seconds = ttl_sec)
  
  db.events.remove(
    {'created_at': {'$lt': max_age}}, True)

  db.events_test.remove(
    {'created_at': {'$lt': max_age}}, True)
    
  print "Removed events older than: %s" % str(max_age) 

def main():
  """Parse arguments and call collect_garbage"""
  
  parser = argparse.ArgumentParser(description="RSE Garbage Collector")
  parser.add_argument('--mongodb-host', type=str, default="127.0.0.1", help="mongod/mongos host (127.0.0.1)")
  parser.add_argument('--mongodb-port', type=int, default=27017, help="mongod/mongos port (27017)")
  parser.add_argument('--mongodb-database', type=str, default="rse", help="Name of event database (rse)")
  parser.add_argument('--ttl', type=int, default=2*60 + 10, help="TTL, in seconds, for events. Should be just over 2x slowest client polling frequency (2 mins, 10 secs)")
  
  args = parser.parse_args()
  for i in range(10):
    try:
      remove_expired_events(args.mongodb_host, args.mongodb_port, args.mongodb_database, args.ttl)
      break
    except pymongo.errors.AutoReconnect:
      time.sleep(1)

# If running this script directly, execute the "main" routine
if __name__ == "__main__":
  main()
