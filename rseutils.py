#!/usr/bin/env python

"""
@file rseutils.py
@author Kurt Griffiths
$Author$  <=== populated-by-subversion
$Revision$  <=== populated-by-subversion
$Date$  <=== populated-by-subversion

@brief
RSE utility functions
"""
import time

# Returns a long ID based on the current POSIX time with (at least) microsecond precision
def time_id():
  return long((time.time() - 1302000000) * 100000)