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
import sys
import time
import logging
import logging.config

from . import config
from pkg_resources import get_distribution


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


def filter_dataset(dataset, keyset):
    """ Get a subset of keys from a nested dict structure

    This is ugly and I don't like it, but it works. Both inputs are
    nested structures. This walks 'keyset' until it finds a sequence,
    and then filters the corresponding element of 'dataset', removing
    all items not in the keyset.

    It's intended to pare down the huge structures returned by various
    mongo diagnostics to just the elements we actually want.
    """

    if isinstance(keyset, dict):
        out = dataset
        for key, sub_keyset in keyset.items():
            out[key] = filter_dataset(out[key], sub_keyset)
        return out

    out = {}
    str_keys = [item for item in keyset if isinstance(item, str)]
    dct_keys = [item for item in keyset if isinstance(item, dict)]
    include = [k for k in str_keys if k in dataset]
    recurse = {key: subkeys for key, subkeys
               in mergedicts(dct_keys).items()
               if key in dataset}

    for key in include:
        out[key] = dataset[key]
    for key, subkeys in recurse.items():
        out[key] = filter_dataset(dataset[key], subkeys)

    return out


def mergedicts(dicts):
    """ Merge a sequence of dictionaries. Last collision wins. """
    out = {}
    for d in dicts:
        out.update(d)
    return out


def versions_report():
    """ Get versions of RSE and all dependencies, if possible."""

    rse = get_distribution('rse')
    deps = [get_distribution(req.project_name)
            for req in rse.requires()]
    versions = [('Python', sys.version),
                ('RSE', rse.version)]
    versions.extend((dep.project_name, dep.version) for dep in deps)
    return versions


def initlog(path=None):
    """ Set up logging """
    logconf = config.load('logging.yaml', path)
    logging.config.dictConfig(logconf)
    log.critical("LOGLEVEL ENABLED: CRITICAL")
    log.error("LOGLEVEL ENABLED: ERROR")
    log.warn("LOGLEVEL ENABLED: WARN")
    log.info("LOGLEVEL ENABLED: INFO")
    log.debug("LOGLEVEL ENABLED: DEBUG")
