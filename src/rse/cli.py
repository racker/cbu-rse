#!/usr/bin/python2

import sys

from wsgiref.simple_server import make_server

import rse

# If running rse directly, startup a basic WSGI server for testing
def main():
    conf = None
    if len(sys.argv) > 1:
        conf = sys.argv[1]

    app = rse.RseApplication(conf)
    httpd = make_server('', 8000, app)
    print "Serving on port 8000..."
    httpd.serve_forever()

if __name__ == "__main__":
    main()
