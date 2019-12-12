import unittest 

from rse.rax.http.exceptions import *
from rse.rax.http.rawr import Controller


class HelloTest(Controller):

  def __init__(self, foo):
    pass
  
  def get(self, name):
    self.response.write_header('Content-type','text/plain')
    self.response.write(self.request.get_optional_param('foo', 'Once upon a time...\n'))
    self.response.write('Hello %s!\n' % name)
    

class GoFishTest(Controller):
  def get(self):
    self.response.write('Hello world!\n')    
    raise HttpError(404, 'Go fish!')


class StreamTest(Controller):
  def get(self):
    self.response.write_header('Content-type','text/plain')    

    data = "Row, row, row your boat, gently down the stream!\n"
    self.response.stream = [data]
    self.response.stream_length = len(data)

# @todo: What is the standard unit testing framework for Python? Use that!
# @todo: Test all self.request helper functions
# TODO: push this into a unit testable thing
#if __name__ == "__main__":
#  from wsgiref.simple_server import make_server
#  
#  httpd = make_server('', 8000, testapp)
#  print "Serving on port 8000..."
#  httpd.serve_forever()    


class TestRaxHttp(unittest.TestCase):

    def setup(self):
        # TODO: Make self.testapp servable
        self.testapp = Rawr()    
        self.testapp.add_route(r'/hello/(.*)', HelloTest, dict(foo=1))
        self.testapp.add_route(r'/go-fish$', GoFishTest) # Dollar is necessary to require the entire string be matched
        self.testapp.add_route(re.compile('/stream', re.IGNORECASE), StreamTest)    

    def tearDown(self):
        pass

    # TODO: Add some unit tests!
