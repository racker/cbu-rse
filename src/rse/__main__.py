#!/usr/bin/python2

from wsgiref.simple_server import make_server

import rse

# If running rse directly, startup a basic WSGI server for testing

if __name__ == "__main__":
    app = rse.instantiate()

    httpd = make_server('', 8000, app)
    print "Serving on port 8000..."
    httpd.serve_forever()
