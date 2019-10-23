#!/usr/bin/python2

import sys
import logging
import argparse

from wsgiref.simple_server import make_server

import rse
import yaml


log = logging.getLogger(__name__)

def main():
    """ Start RSE standalone for testing """

    rse.util.initlog()
    log.warn("Starting RSE in standalone mode!")

    log.debug("Reading cli args")
    parser = argparse.ArgumentParser("Really Simple Events")
    parser.add_argument('--conf', help="override conf directory path")
    parser.add_argument('--dbgconf', action='store_true',
                        help="print effective configuration and exit.")
    args = parser.parse_args()

    log.info("Loading configuration")
    path = sys.argv[1] if len(sys.argv) > 1 else None
    conf = rse.config.load('rse.yaml', path)
    if args.dbgconf:
        log.info("Dumping effective configuration, as requested.")
        yaml.dump(conf, default_flow_style=False)
        sys.exit()

    log.info("Creating application")
    app = rse.RseApplication(conf)

    log.info("Making server")
    httpd = make_server('', 8000, app)
    log.info("Serving on port 8000...")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
