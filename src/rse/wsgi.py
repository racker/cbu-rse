# This instantiates the wsgi app for use by gunicorn, e.g.:
#
# `gunicorn rse.wsgi:app`

from rse import RseApplication
from rse import config
from rse.util import initlog

initlog()
conf = config.load('rse.yaml')
app = RseApplication(conf)
