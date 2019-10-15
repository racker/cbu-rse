#!/usr/bin/python2

import sys
import logging

from wsgiref.simple_server import make_server

import rse


# If running rse directly, startup a basic WSGI server for testing
def main():
    rse.util.initlog()

    path = sys.argv[1] if len(sys.argv) > 1 else None
    conf = rse.config.load('rse.yaml', path)

    app = rse.RseApplication(conf)
    httpd = make_server('', 8000, app)
    logging.info("Serving on port 8000...")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
