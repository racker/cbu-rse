import logging
import os
from copy import deepcopy
from os.path import dirname, basename, realpath
from os.path import join as pathjoin

import yaml


log = logging.getLogger(__name__)
# Default conf search paths
CONF_SEARCH_DIRS = [
        os.environ.get('RSE_CONF_DIR'),
        os.path.expanduser('~/.config/rse'),
        "/etc/rse",
        ]


def load(name, path=None):
    """ Load a yaml file and merge it with the config defaults.

    Specifically, this searches:

    - $RSE_CONF_DIR
    - ~/.config/rse
    - /etc/rse

    If path is explicitly provided, search paths are ignored.

    "name" must match one of the defaults files in this directory.
    """

    if not name:
        raise ValueError('canonical filename must be provided')

    # Find out where we're looking
    if path is not None:
        paths = [path]
    else:
        paths = [pathjoin(directory, name)
                 for directory in CONF_SEARCH_DIRS
                 if directory is not None]

    here = pathjoin(dirname(realpath(__file__)))
    defaults_path = pathjoin(here, name)
    log.debug("Loading %s defaults from %s", name, defaults_path)
    with open(defaults_path) as f:
        dataset = yaml.safe_load(f.read())

    for path in paths:
        log.debug("looking for %s at %s", name, path)
        try:
            with open(path) as conf_file:
                log.debug("found %s at %s", name, path)
                overrides = yaml.safe_load(conf_file.read())
            log.debug("loaded %s from %s", name, path)
            break
        except IOError:
            pass
    else:
        msg = "couldn't find %s anywhere, using defaults only"
        log.warn(msg, name)
        overrides = {}

    merge(dataset, overrides)
    return dataset


def merge(dataset, overrides):
    """ Recursively merge two nested dictionaries.

    This probably isn't fully general, but since it only has to handle
    our own conf file it should be good enough.  Note that this modifies
    `dataset` in-place!
    """

    for key, node in overrides.items():
        tgtnode = dataset.setdefault(key, {})
        if isinstance(node, dict) and isinstance(tgtnode, dict):
                merge(tgtnode, node)
        else:
            dataset[key] = node

    return dataset


def convert(dataset, keypath, converter, sep=":", replace=True):
    """ Process a nested dictionary key

    Sometimes deeply-nested config values are supplied as strings, but
    we actually want some object generated from that string. Code
    handling that case tends to involve repetitive and ugly nested-dict
    accesses.

    `remap` traverses a nested dictionary, where `keypath` is a
    colon-separated list of nested strings. When the target value is
    reached, `converter` (typically a lambda) is called on it; the result
    replaces the original value.

    Commonly raises KeyError (if the path doesn't exist) or TypeError
    (if the keypath's value is None)

    Example:

    convert(dataset, "path:to:ssl_version", lambda s: getattr(ssl, s))

    This looks at the string at dataset['ssl_options']['ssl_version'],
    and replaces it with the corresponding protocol attribute from the
    ssl module.

    Callers should probably use convert_all below in most cases.
    """
    parent = None
    node = dataset
    keys = keypath.split(sep)

    for k in keys:
        parent = node
        node = node[k]

    newval = converter(node)
    if replace:
        log.debug("conf conversion: %s -> %s", node, newval)
        parent[keys[-1]] = newval

    return newval


def process(dataset, converter_table):
    """ Remap all items in converter_table

    converter_table: a dict mapping nested-key strings to conversion functions

    Returns an entirely new dataset. Keys that aren't present, or that
    fail conversion on account of being set to None, are ignored.
    """

    new_dataset = deepcopy(dataset)
    for keypath, converter in converter_table.items():
        try:
            convert(new_dataset, keypath, converter)
        except (KeyError, TypeError):
            # If a key isn't provided, ignore it.
            # FIXME: should distinguish between "explicit None
            # encountered" and "something else is broken"
            pass
    return new_dataset
