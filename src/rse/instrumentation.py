import contextlib
import logging
from unittest.mock import Mock

try:
    import newrelic.agent as nr
except ImportError:
    nr = Mock(spec_set=['set_transaction_name'])
try:
    import elasticapm
except ImportError:
    elasticapm = Mock(spec_set=['Client',
                                'set_transaction_name',
                                'begin_transaction',
                                'end_transaction'])


NR_AVAILABLE = not isinstance(nr, Mock)
EAPM_AVAILABLE = not isinstance(elasticapm, Mock)
log = logging.getLogger(__name__)


class Transaction(contextlib.ContextDecorator):
    """ Transaction context manager

    Use this to ensure start/end calls happen for instrumentation transactions.
    If you need to set the name of the transaction after creation, you can
    either set the name attribute or call the set_name staticmethod.

    The second argument is the rawr controller handling the transaction. It
    needs to have request/response attributes. These are used to get the
    response status code.
    """

    def __init__(self, name, controller):
        self.name = name
        self.controller = controller

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.set_name(self._name)

    def __enter__(self):
        elasticapm.get_client().begin_transaction('request')
        self.set_name(self._name)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        result = getattr(exc_value, 'status', self.controller.response.status)
        elasticapm.get_client().end_transaction(self.name, result)
        return False

    @staticmethod
    def set_name(name):
        """ Set the transaction name for all available instrumentation libs """
        for obj in nr, elasticapm:
            obj.set_transaction_name(name)


def instrument(app):
    """ Instrument a WSGI application

    Returns the app object, possibly wrapped.
    """
    msg_ok = "%s custom instrumentation enabled"
    msg_bad = "%s not available (module not importable?)"
    modules = {'ElasticAPM': EAPM_AVAILABLE,
               'Newrelic': NR_AVAILABLE}
    for name, available in modules.items():
        log.info(msg_ok if available else msg_bad, name)
    elasticapm.instrument()
    return nr.WSGIApplicationWrapper(app) if NR_AVAILABLE else app
