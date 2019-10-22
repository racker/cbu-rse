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
import logging
import logging.config

from . import config


log = logging.getLogger(__name__)


def time_id(offset_sec=0):
    """Returns a long ID based on the current POSIX time with (at least)
     microsecond precision"""

    # Convert floating point timestamp to a long with plenty of headroom.
    # Note: 1302000000 is an arbitrary epoch/offset used to free up some bits
    return long((time.time() - 1302000000 + offset_sec) * 100000)


def splitport(nodestring, defaultport):
    """ Turn host strings into server/port tuples"""
    try:
        host, port = nodestring.split(':')
    except ValueError:  # Produced when no :port is specified
        host, port = nodestring, defaultport
    return (host, int(port))


def initlog(path=None):
    """ Set up logging """
    logconf = config.load('logging.yaml', path)
    logging.config.dictConfig(logconf)
    log.critical("LOGLEVEL ENABLED: CRITICAL")
    log.error("LOGLEVEL ENABLED: ERROR")
    log.warn("LOGLEVEL ENABLED: WARN")
    log.info("LOGLEVEL ENABLED: INFO")
    log.debug("LOGLEVEL ENABLED: DEBUG")
