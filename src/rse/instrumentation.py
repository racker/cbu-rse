import logging
from .util import noop

try:
    import newrelic.agent as nr
    add_custom_parameter = nr.add_custom_parameter
except ImportError:
    nr = None
    add_custom_parameter = noop
try:
    import elasticapm
    eclient = elasticapm.get_client()
except ImportError:
    elasticapm = None
    eclient = None


log = logging.getLogger(__name__)


def instrument(app):
    """ Instrument a WSGI application

    Returns the app object, possibly wrapped for instrumentation.
    """
    msg_ok = "%s custom instrumentation enabled"
    msg_bad = "%s not available (module not importable?)"
    modules = {'ElasticAPM': elasticapm,
               'Newrelic': nr}
    for name, available in modules.items():
        log.info(msg_ok if available else msg_bad, name)
    if elasticapm:
        elasticapm.instrument()
    return nr.WSGIApplicationWrapper(app) if nr else app


def begin_transaction(name):
    if elasticapm:
        eclient.begin_transaction('request')
        elasticapm.set_transaction_name(name)


def set_transaction_name(name):
    for module in nr, elasticapm:
        if module:
            module.set_transaction_name(name)


def end_transaction(result):
    if eclient:
        eclient.end_transaction(result=result)
