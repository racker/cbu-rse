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

@todo
Turn this into an installable package (?) so it can be shared between components

@todo
Add routing
"""

import webob
from httpex import *

# Responsible for routing (set in initialization as a dictionary)
class Rawr:
  # Speeds up member variable access and reduces memory usage
  __slots__ = ['controller', 'controller_kwargs']

  def __init__(self, controller, kwargs = {}):
    self.controller = web_service
    self.controller_kwargs = kwargs
    
  def __call__(self, environ, start_response):
    return self.controller(**self.controller_kwargs)(environ, start_response)
    
# Represents an incoming web request. Adds some helpers to webob.Request.
class Request(webob.Request):
  def __init__(self, environ):
    webob.Request.__init__(self, environ)
  
  # Returns the specified query string paramter, or a default value if the 
  # paramter was not specified in the URL.
  def optional_param(self, param_name, default_value):
    # Note: This approach should be more efficient than handling exceptions...
    # but only if it is common to not have this param  
    return self.GET[param_name] if self.GET.has_key(param_name) else default_value
    
  # Returns the specified query string parameter or throws an HttpException if not found
  def param(self, param_name):
    try:
      return self.GET[param_name]
    except:
      raise HttpBadRequest('Missing query parameter: %s' % param_name)
    
  # Faster than handling exceptions if common to not have this header
  def optional_header(self, header_name, default_value):
    return self.headers[header_name] if self.headers.has_key(header_name) else default_value
  
  # Returns a required header (throws HttpException if header not found)
  def header(self, header_name):
    try:
       return self.headers[header_name]
    except:
      raise HttpBadRequest('Missing header: %s' % header_name)
   
# Represents the outgoing web service response
class Response:
  # Speeds up member variable access and reduces memory usage
  __slots__ = ['response_body', 'response_headers', 'status', 'stream', 'stream_length']
  
  def __init__(self):
    self.response_body = '' 
    self.response_headers = []
    self.status = '200 OK'
    self.stream = None
    self.stream_length = 0
        
  def write(self, str):
    self.response_body += str
    pass

  def write_header(self, header, value):
    self.response_headers.append((header, value))
    pass
    
# Base class for Rawr controllers.
#
# To use, inherit from this class and implement methods corresponding to the
# HTTP verbs you want to handle (e.g., get, put, post, delete, head)
#
# Inside your child class, you can access self.request and self.response in
# order to parse the client request and build a response, respectively.
#
# self.request inherits from webob.Request and adds some helper functions. On
# the other hand, self.response does NOT inherit from webob.Response for 
# performance reasons.
#
# Raise one of the httpex.* exception classes within your code to return an
# HTTP status other than "200 OK"
# 
# Note: Content-Length is automatically set for you unless using self.request.stream,
# in which case you will need to set self.request.stream_length yourself.
class Controller:
  # Speeds up member variable access and reduces memory usage
  __slots__ = ['request', 'response']
    
  def __call__(self, environ, start_response):
    self.request = Request(environ)
    self.response = Response()

    try:
      getattr(self, 'prepare')()
      getattr(self, self.request.method.lower())()

    except HttpError, e:
      start_response(e.status(), [('Content-type','text/plain')])
      return [e.info]

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


class HelloTest(Controller):
  def __init__(self, foo):
    pass
  
  def get(self):
    self.response.write_header('Content-type','text/plain')
    self.response.write(self.request.optional_param('foo', 'Once upon a time...\n'))
    self.response.write('Hello world!\n')
    
class GoFishTest(Controller):
  def get(self):
    self.response.write(self.request.optional_param('foo', 'Once upon a time...\n'))
    self.response.write('Hello world!\n')
    
    raise HttpError(404, 'Go fish!')
      
class StreamTest(Controller):
  def get(self):
    self.response.write_header('Content-type','text/plain')    

    data = "Row, row, row your boat, gently down the stream!\n"
    self.response.stream = [data]
    self.response.stream_length = len(data)

testapp_hello = Rawr(HelloTest, dict(foo=1))      
testapp_go_fish = Rawr(GoFishTest)      
testapp_stream = Rawr(StreamTest)      

# @todo: What is the standard unit testing framework for Python? Use that!
if __name__ == "__main__":
  from wsgiref.simple_server import make_server
  
  httpd = make_server('', 8000, testapp_hello)
  print "Serving on port 8000..."
  httpd.serve_forever()    

