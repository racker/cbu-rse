# This instantiates the wsgi app for use by gunicorn, e.g.:
#
# `gunicorn rse.wsgi:app`

import logging

from rse import RseApplication
from rse import config
from rse.util import initlog, nr

log = logging.getLogger(__name__)

initlog()

log.info("Loading configuration")
conf = config.load('rse.yaml')
log.info("Creating wsgi app")
app = RseApplication(conf)

if nr:
    app = nr.WSGIApplicationWrapper(app)
    log.info("Newrelic custom instrumentation enabled")
else:
    log.info("Newrelic customizations not available (module not importable?)")
log.info("App ready")
