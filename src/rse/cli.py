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
    parser = argparse.ArgumentParser(description="Really Simple Events")
    parser.add_argument('--conf', help="override conf directory path")
    parser.add_argument('--port', default=8000, help="listen port")
    parser.add_argument('--dbgconf', action='store_true',
                        help="print effective configuration and exit.")
    args = parser.parse_args()


    conf = rse.config.load('rse.yaml', args.conf)
    if args.dbgconf:
        log.info("Dumping effective configuration, as requested.")
        yaml.dump(conf, default_flow_style=False)
        sys.exit()

    rse.util.initlog()
    log.warn("Starting RSE in standalone mode!")

    log.debug("Creating application")
    app = rse.RseApplication(conf)

    log.debug("Making server")
    httpd = make_server('', args.port, app)
    log.info("Serving on port %s...", args.port)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
