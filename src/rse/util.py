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
from functools import partial, partialmethod

from . import config
from pkg_resources import get_distribution


log = logging.getLogger(__name__)
httplog = logging.getLogger(__name__ + '.httplog')

# The intent here is that code that wants to use newrelic can just do if nr:
# nr.whatever, rather than having to do import fallback boilerplate. Even
# better would be a mock nr object that provides noops in place of newrelic
# functions, so callers don't have to know or care whether it's present.
try:
    import newrelic.agent as nr
except ImportError:
    nr = None

# For elasticapm we need to instantiate the client object and pass it around
# as needed to begin and end transactions. Some functionality requires calling
# methods of elasticapm directly, so we make both the base module and the
# client object available to import from rse.util.
try:
    import elasticapm
    apm = elasticapm.Client()
except ImportError:
    elasticapm, apm = None, None


def time_id(offset_sec=0):
    """Returns a long ID based on the current POSIX time with (at least)
     microsecond precision"""

    # Convert floating point timestamp to a long with plenty of headroom.
    # Note: 1302000000 is an arbitrary epoch/offset used to free up some bits
    return int((time.time() - 1302000000 + offset_sec) * 100000)


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
        for key, sub_keyset in list(keyset.items()):
            out[key] = filter_dataset(out[key], sub_keyset)
        return out

    out = {}
    str_keys = [item for item in keyset if isinstance(item, str)]
    dct_keys = [item for item in keyset if isinstance(item, dict)]
    include = [k for k in str_keys if k in dataset]
    recurse = {key: subkeys for key, subkeys
               in list(mergedicts(dct_keys).items())
               if key in dataset}

    for key in include:
        out[key] = dataset[key]
    for key, subkeys in list(recurse.items()):
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
    """ Set up logging

    This does some evil monkeypatching to create a "trace" loglevel and
    make it usable like any other. The *right* way to do this is to
    subclass Logger and use setLoggerClass, but I can't figure out a way
    to guarantee that happens before any loggers are intantiated. This
    does the job well enough.

    Most of the method comes from this SO answer:
    https://stackoverflow.com/a/35804945/
    """

    tracelvl = logging.DEBUG - 5
    logcls = logging.getLoggerClass()
    name = 'TRACE'

    logging.TRACE = tracelvl
    logging.addLevelName(tracelvl, name)
    logging.trace = partial(logging.log, tracelvl)
    logcls.trace = partialmethod(logcls.log, tracelvl)

    logconf = config.load('logging.yaml', path)
    logging.config.dictConfig(logconf)
    log.critical("LOGLEVEL ENABLED: CRITICAL")
    log.error("LOGLEVEL ENABLED: ERROR")
    log.warning("LOGLEVEL ENABLED: WARN")
    log.info("LOGLEVEL ENABLED: INFO")
    log.debug("LOGLEVEL ENABLED: DEBUG")
    log.trace("LOGLEVEL ENABLED: TRACE")
    if httplog.isEnabledFor(logging.TRACE):
        msg = ('WARNING: HTTP REQUEST LOGGING ENABLED. If this message '
               'appears more than once, you are running multiple RSE '
               'workers and their request logs may interlace.')
        log.warning(msg)
