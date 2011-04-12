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

class HttpError(Exception):
  def __init__(self, status_code, info = ''):
    self.status_code = status_code
    self.info = info
    self.info += '\n'
    
  def status(self):
    return '%d %s' % (self.status_code, httplib.responses[self.status_code])
    
class HttpNotFound(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 404, message)
    
class HttpNoContent(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 204, message)
    
class HttpBadRequest(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 400, message)
    
class HttpForbidden(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 403, message)
    
class HttpMethodNotAllowed(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 405, message)
        
class HttpPreconditionFailed(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 412, message)

class HttpUnsupportedMediaType(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 415, message)    
    
class HttpConflict(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 409, message)

class HttpInternalServerError(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 500, message)
    
class HttpCreated(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 201, message)
    
class HttpAccepted(HttpError):
  def __init__(self, message = ''):
    HttpError.__init__(self, 202, message)
