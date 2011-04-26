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
import rseutils

def remove_expired_events(host, port, db_name, ttl_sec):
  """Removes events from the specified database that have expired based on ttl_sec"""
  
  connection = pymongo.Connection(host, port)
  db = connection[db_name]
  
  # Use the same formula that raxSvcRse.py uses to create IDs
  timeout = rseutils.time_id(-1 * ttl_sec)  
  
  db.events.remove(
    {'_id': {'$lt': timeout}}, True)
    
  print "Removed items older than: %d" % timeout

def main():
  """Parse arguments and call collect_garbage"""
  
  parser = argparse.ArgumentParser(description="RSE Garbage Collector")
  parser.add_argument('--mongodb-host', type=str, default="127.0.0.1", help="mongod/mongos host (127.0.0.1)")
  parser.add_argument('--mongodb-port', type=int, default=27017, help="mongod/mongos port (27017)")
  parser.add_argument('--mongodb-database', type=str, default="rse", help="Name of event database (rse)")
  parser.add_argument('--ttl', type=int, default=2*60 + 10, help="TTL, in seconds, for events. Should be just over 2x slowest client polling frequency (2 mins, 10 secs)")
  
  args = parser.parse_args()
  remove_expired_events(args.mongodb_host, args.mongodb_port, args.mongodb_database, args.ttl)

# If running this script directly, execute the "main" routine
if __name__ == "__main__":
  main()