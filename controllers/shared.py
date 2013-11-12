"""
@file shared.py
@author Kurt Griffiths

@brief
Defines the Shared class, which encapsulates performance counters and
hard-coded options
"""

import re


class Shared:
    """Encapsulates performance counters and hard-coded options"""
    def __init__(self, logger, authtoken_cache):
        self.authtoken_cache = authtoken_cache
        self.logger = logger

        self.cache_token_hitcnt = 0
        self.cache_token_totalcnt = 0
        self.id_totalcnt = 0
        self.id_retrycnt = 0

        self.AUTH_ENDPOINT = '/v1.0/auth/isauthenticated'
        self.AUTH_HEALTH_ENDPOINT = '/v1.0/help/apihealth'

        # Precompiled regex for validating JSONP callback name
        self.JSONP_CALLBACK_PATTERN = re.compile("\A[a-zA-Z0-9_]+\Z")
