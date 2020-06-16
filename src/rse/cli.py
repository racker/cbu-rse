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
    parser.add_argument('--debug', action='store_true',
                        help="enable debug mode.")
    parser.add_argument('-V', '--version', action='store_true',
                        help="print version and exit")
    parser.add_argument('--versions', action='store_true',
                        help="print version of RSE and all dependencies")
    args = parser.parse_args()

    conf = rse.config.load('rse.yaml', args.conf)
    if args.version:
        from rse.version import version
        print(version)
        sys.exit()

    if args.versions:
        for name, ver in rse.util.versions_report():
            print('{}\t{}'.format(name, ver))
        sys.exit()

    if args.dbgconf:
        print(yaml.dump(conf, default_flow_style=False))
        sys.exit()

    rse.util.initlog()

    log.warn("Starting RSE in standalone mode!")

    try:
        log.debug("Creating application")
        app = rse.RseApplication(conf)
        log.debug("Making server")
        httpd = make_server('', args.port, app)
        log.info("Serving on port %s...", args.port)
        httpd.serve_forever()
    except Exception as e:
        log.critical(e)
        if args.debug:
            raise
        else:
            sys.exit(2)


if __name__ == "__main__":
    main()
