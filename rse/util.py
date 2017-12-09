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


def time_id(offset_sec=0):
    """Returns a long ID based on the current POSIX time with (at least)
     microsecond precision"""

    # Convert floating point timestamp to a long with plenty of headroom.
    # Note: 1302000000 is an arbitrary epoch/offset used to free up some bits
    return long((time.time() - 1302000000 + offset_sec) * 100000)
