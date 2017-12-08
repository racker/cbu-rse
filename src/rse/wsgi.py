# This instantiates the wsgi app for use by gunicorn, e.g.:
#
# `gunicorn rse.wsgi:app`

import rse

app = rse.instantiate()
