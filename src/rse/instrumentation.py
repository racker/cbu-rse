""" Instrumentation abstractions

This file abstracts the newrelic and elasticapm instrumentation functions.
The intent is to allow other parts of the program to instrument things
without having to know or care whether a particular backend is enabled or even
available.
"""

import logging

from .util import noop

try:
    import newrelic.agent as nr
    add_custom_parameter = nr.add_custom_parameter  # pylint: disable=invalid-name
except ImportError:
    nr = None
    add_custom_parameter = noop  # pylint: disable=invalid-name
try:
    import elasticapm
    eclient = elasticapm.get_client()  # pylint: disable=invalid-name
except ImportError:
    elasticapm = None
    eclient = None  # pylint: disable=invalid-name


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
    """ Start a transaction """
    if elasticapm:
        eclient.begin_transaction('request')
        elasticapm.set_transaction_name(name)


def set_transaction_name(name):
    """ Set the name of the current transaction """
    for module in nr, elasticapm:
        if module:
            module.set_transaction_name(name)


def end_transaction(result):
    """ End the current transaction

    `result` should be the status code of the response.
    """
    if eclient:
        eclient.end_transaction(result=result)
