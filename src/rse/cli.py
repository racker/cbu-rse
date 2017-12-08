#!/usr/bin/python2

from wsgiref.simple_server import make_server

import rse

# If running rse directly, startup a basic WSGI server for testing
def main():
    app = rse.RseApplication()
    httpd = make_server('', 8000, app)
    print "Serving on port 8000..."
    httpd.serve_forever()

if __name__ == "__main__":
    main()
