# This instantiates the wsgi app for use by gunicorn, e.g.:
#
# `gunicorn rse.wsgi:app`

import logging

from rse import RseApplication
from rse import config
from rse.util import initlog
from rse.instrumentation import instrument

log = logging.getLogger(__name__)

initlog()

log.info("Loading configuration")
conf = config.load('rse.yaml')
log.info("Creating wsgi app")
app = instrument(RseApplication(conf), conf)


log.info("App ready")
