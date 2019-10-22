#!/usr/bin/python2

import sys
import logging

from wsgiref.simple_server import make_server

import rse


log = logging.getLogger(__name__)

# If running rse directly, startup a basic WSGI server for testing
def main():
    rse.util.initlog()
    log.warn("Starting RSE in standalone mode!")

    path = sys.argv[1] if len(sys.argv) > 1 else None
    log.info("Looking for conf files")
    conf = rse.config.load('rse.yaml', path)
    log.info("Conf file loaded")

    log.info("Creating application")
    app = rse.RseApplication(conf)
    log.info("Application created")

    log.info("Making server")
    httpd = make_server('', 8000, app)
    log.info("Serving on port 8000...")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
