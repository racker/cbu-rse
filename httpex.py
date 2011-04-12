"""
@file httpex.py
@author Kurt Griffiths
$Author: kurt $  <=== populated-by-subversion
$Revision: 835 $  <=== populated-by-subversion
$Date: 2011-01-10 14:15:28 -0500 (Mon, 10 Jan 2011) $  <=== populated-by-subversion

@brief
HTTP exceptions

@pre
Requires Python 2.x (tested with 2.7)
"""

import httplib

# Represents a generic HTTP error status. Raise this or one of the
# predefined child classes to return a status other than "200 OK"
# from a Rawr controller
class HttpError(Exception):
  def __init__(self, status_code, info = ''):
    self.status_code = status_code
    self.info = info
    self.info += '\n'
    
  def status(self):
    return '%d %s' % (self.status_code, httplib.responses[self.status_code])

# 404 Not Found    
class HttpNotFound(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 404, message)
    
# 204 No Content
class HttpNoContent(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 204, message)
    
# 400 Bad Request
class HttpBadRequest(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 400, message)
    
# 403 Forbidden
class HttpForbidden(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 403, message)
    
# 405 Method Not Allowed
class HttpMethodNotAllowed(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 405, message)
        
# 412 Precondition Failed
class HttpPreconditionFailed(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 412, message)

# 415 Unsupported Media Type
class HttpUnsupportedMediaType(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 415, message)    
    
# 409 Conflict
class HttpConflict(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 409, message)

# 500 Internal Server Error
class HttpInternalServerError(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 500, message)
    
# 201 Created    
class HttpCreated(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 201, message)
    
# 202 Accepted    
class HttpAccepted(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 202, message)
