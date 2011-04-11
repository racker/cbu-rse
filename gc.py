#!/usr/bin/env python

"""
@file gc.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
RSE garbage collector. Requires Python 2.7 or better, argparse, and pymongo
"""

import pymongo
import argparse
import time

# Removes events from the specified database that have expired based on ttl_sec
def remove_expired_events(host, port, db_name, ttl_sec):
  connection = pymongo.Connection(host, port)
  db = connection[db_name]
  
  # Use the same formula that raxSvcRse.py uses to create IDs
  timeout = long((time.time() - 1302000000) * 100000) - ttl_sec 
  print timeout
  
  db.events.remove(
    {'_id': {'$lt': timeout}}, True)

# Parse arguments and call collect_garbage
def main():
  parser = argparse.ArgumentParser(description="RSE Garbage Collector")
  parser.add_argument('--mongodb-host', type=str, default="127.0.0.1", help="mongod/mongos host (127.0.0.1)")
  parser.add_argument('--mongodb-port', type=int, default=27017, help="mongod/mongos port (27017)")
  parser.add_argument('--mongodb-database', type=str, default="rse", help="Name of event database (rse)")
  parser.add_argument('--ttl', type=int, default=5*60, help="TTL, in seconds, for events (300)")
  
  args = parser.parse_args()
  remove_expired_events(args.mongodb_host, args.mongodb_port, args.mongodb_database, args.ttl)

# If running this script directly, execute the "main" routine
if __name__ == "__main__":
  main()