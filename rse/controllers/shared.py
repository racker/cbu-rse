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
    def __init__(self, logger):
        self.logger = logger

        self.id_totalcnt = 0
        self.id_retrycnt = 0

        # Precompiled regex for validating JSONP callback name
        self.JSONP_CALLBACK_PATTERN = re.compile("\A[a-zA-Z0-9_]+\Z")
