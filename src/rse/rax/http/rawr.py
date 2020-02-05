"""
@file rawr.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
Rawr is a micro WSGI/REST framework designed for simplicity and speed. Run behind gunicorn + nginx

@pre
Requires Python 2.7 and webob
"""

import http.client
import re
import webob
from .exceptions import *

class Rawr:
    """Responsible for routing (set in initialization as a dictionary)"""

    def __init__(self):
        self.routes = []

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = Response()

        try:
            for route in self.routes:
                match = route[0].match(request.path)

                if match:
                    kwargs = dict((k, v) for (k, v) in match.groupdict().items())
                    args = None

                    # match.groups() includes both named and unnamed groups, so
                    # we want to use either groups or groupdict but not both.
                    if kwargs:
                        args = []
                    else:
                        args = [s for s in match.groups()]

                    return route[1](**route[2])(request, response, start_response, *args, **kwargs)

            raise HttpNotFound('URI not found: ' + request.path)

        except HttpError as ex:
            start_response(ex.status(), [('Content-type','application/json; charset=utf-8')])
            return ['{{ "message": "{}" }}'.format(ex.info).encode()]

    def add_route(self, pattern, controller, kwargs = {}):
        if type(pattern) is str:
            pattern = re.compile(pattern)

        self.routes.append((pattern, controller, kwargs))


class Request(webob.Request):
    """Represents an incoming web request. Adds some helpers to webob.Request."""

    def __init__(self, environ):
        webob.Request.__init__(self, environ)

    # Returns the specified query string paramter, or a default value if the
    # paramter was not specified in the URL.
    def get_optional_param(self, param_name, default_value = None):
        # Note: This approach should be more efficient than handling exceptions...
        # but only if it is common to not have this param
        return self.GET[param_name] if param_name in self.GET else default_value

    # Returns the specified query string parameter or throws an HttpException if not found
    def get_param(self, param_name):
        try:
            return self.GET[param_name]
        except:
            raise HttpBadRequest('Missing query parameter: %s' % param_name)

    # Faster than handling exceptions if common to not have this header
    def get_optional_header(self, header_name, default_value = None):
        return self.headers[header_name] if header_name in self.headers else default_value

    # Returns a required header (throws HttpException if header not found)
    def get_header(self, header_name):
        try:
            return self.headers[header_name]
        except:
            raise HttpBadRequest('Missing header: %s' % header_name)

class Response:
    """Represents the outgoing web service response"""

    # Speeds up member variable access and reduces memory usage
    __slots__ = ['response_body', 'response_headers', 'status', 'stream', 'stream_length']

    def __init__(self):
        self.response_body = b''
        self.response_headers = []
        self.status = '200 OK'
        self.stream = None
        self.stream_length = 0

    def write(self, str):
        self.response_body += str.encode()
        pass

    def write_header(self, header, value):
        self.response_headers.append((header, value))
        pass

    def set_status(self, status_code):
        self.status = '%d %s' % (status_code, http.client.responses[status_code])

class Controller:
    """
    Base class for Rawr controllers.

    To use, inherit from this class and implement methods corresponding to the
    HTTP verbs you want to handle (e.g., get, put, post, delete, head)

    Define a prepare method to run code before every request.

    Inside your child class, you can access self.request and self.response in
    order to parse the client request and build a response, respectively.

    self.request inherits from webob.Request and adds some helper functions. On
    the other hand, self.response does NOT inherit from webob.Response for
    performance reasons.

    Raise one of the httpex.* exception classes within your code to return an
    HTTP status other than "200 OK"

    Note: Content-Length is automatically set for you unless using self.request.stream,
    in which case you will need to set self.request.stream_length yourself.
    """

    #Speeds up member variable access and reduces memory usage
    __slots__ = ['request', 'response']

    def __call__(self, request, response, start_response, *args, **kwargs):
        self.request = request
        self.response = response

        getattr(self, 'prepare')()
        getattr(self, self.request.method.lower())(*args, **kwargs)

        if self.response.stream == None:
            self.response.stream = [self.response.response_body]
            self.response.stream_length = len(self.response.response_body)

        self.response.response_headers.append(('Content-Length', str(self.response.stream_length)))

        start_response(self.response.status, self.response.response_headers)
        return self.response.stream

    # Provide stub to avoid being slowed down by getattr exceptions
    def prepare(self):
        pass

    # Provide stub to avoid being slowed down by getattr exceptions
    def get(self):
        raise HttpMethodNotAllowed("GET")

    # Provide stub to avoid being slowed down by getattr exceptions
    def put(self):
        raise HttpMethodNotAllowed("PUT")

    # Provide stub to avoid being slowed down by getattr exceptions
    def post(self):
        raise HttpMethodNotAllowed("POST")

    # Provide stub to avoid being slowed down by getattr exceptions
    def delete(self):
        raise HttpMethodNotAllowed("DELETE")

    # Provide stub to avoid being slowed down by getattr exceptions
    def head(self):
        raise HttpMethodNotAllowed("HEAD")

    # Provide stub to avoid being slowed down by getattr exceptions
    def options(self):
        raise HttpMethodNotAllowed("OPTIONS")
