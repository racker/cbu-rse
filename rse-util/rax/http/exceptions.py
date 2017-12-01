"""
@file exceptions.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
HTTP exceptions (see also http://en.wikipedia.org/wiki/List_of_HTTP_status_codes)

@pre
Requires Python 2.x (tested with 2.7)

@todo
Convert class comments to python-style 
"""

import httplib

# Represents a generic HTTP error status. Raise this or one of the
# predefined child classes to return a status other than "200 OK"
# from a Rawr controller
class HttpError(Exception):
  __slots__ = ['status_code', 'info']
  
  def __init__(self, status_code, info = ''):
    self.status_code = status_code
    self.info = info

  def __str__(self):
    return "HttpError: %d (%s)" % (self.status_code, self.info)
    
  def status(self):
    return '%d %s' % (self.status_code, httplib.responses[self.status_code])
   
# 204 No Content
class HttpNoContent(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 204, info)
    
# 201 Created    
class HttpCreated(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 201, info)
    
# 202 Accepted    
class HttpAccepted(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 202, info)
    
# 400 Bad Request
class HttpBadRequest(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 400, info)
    
# 401 Unauthorized
class HttpUnauthorized(HttpError):
  # Don't return a reason (security best practice)
  def __init__(self):
    HttpError.__init__(self, 401)
    
# 403 Forbidden
class HttpForbidden(HttpError):
  # Don't return a reason (security best practice)
  def __init__(self):
    HttpError.__init__(self, 403)
    
# 404 Not Found    
class HttpNotFound(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 404, info)
    
# 405 Method Not Allowed
class HttpMethodNotAllowed(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 405, info)
        
# 412 Precondition Failed
class HttpPreconditionFailed(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 412, info)

# 415 Unsupported Media Type
class HttpUnsupportedMediaType(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 415, info)    
    
# 409 Conflict
class HttpConflict(HttpError):
  def __init__(self, info = ''):
    HttpError.__init__(self, 409, info)

# 500 Internal Server Error
class HttpInternalServerError(HttpError):
  def __init__(self):
    HttpError.__init__(self, 500)
    
# 502 Bad Gateway
# The server was acting as a gateway or proxy and received an invalid response from the upstream server.
class HttpBadGateway(HttpError):
  def __init__(self):
    HttpError.__init__(self, 502)

# 503 Service Unavailable
class HttpServiceUnavailable(HttpError):
  def __init__(self):
    HttpError.__init__(self, 503)
