"""
@file shared.py
@author Kurt Griffiths

@brief
Defines the Shared class, which encapsulates performance counters and
hard-coded options
"""

import re
import logging

log = logging.getLogger(__name__)


class Shared:
    """Encapsulates performance counters and hard-coded options"""
    def __init__(self, authtoken_cache, test_mode):
        self.authtoken_cache = authtoken_cache
        self.test_mode = test_mode

        self.id_totalcnt = 0
        self.id_retrycnt = 0

        # Precompiled regex for validating JSONP callback name
        self.JSONP_CALLBACK_PATTERN = re.compile("\A[a-zA-Z0-9_]+\Z")
