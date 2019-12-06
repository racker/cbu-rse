#!/usr/bin/env python

from time import time, sleep
from random import random

"""
fastcache.py
Author: Jamie Painter

A fast, just-in-time, in-memory cache for storing tokens/strings/objects which may expire.

Note 1: This module is not thread-safe
Note 2: All times are expessed in seconds
Note 3: Cache purging is only as fine-grained as the resolution. A cached value
        may expire +/- the slice size.
"""


class FastCacheException(Exception):
    pass


class FastCache:

    def __init__(self, retention_period, slice_size):
        """Creates a new fastcache instance.

        param: retention_period Retention period for cached object (in secs)
        param: slice_size Size of a time slice (in secs)
        """
        if retention_period % slice_size != 0:
            raise FastCacheException(
                "Retention period must be evenly divisible by the slice_size")

        self._slice_size = slice_size
        self._slice_count = retention_period // self._slice_size

        self._retention_period = retention_period

        self._current_time = int(time())
        self._last_time = self._current_time  # Time of the last cache insert
        self._last_slice = self._timetoslice(self._last_time)

        self.clear()

    def cache(self, value):
        """Caches the specified value.

        Throws a FastCacheException if the value is already cached.
        """
        # This call will purge (which also sets self._current_time)
        if self.is_cached(value):
            raise FastCacheException("Value already cached")

        self._time_hash[self._current_slice].append(value)
        self._values[value] = True

    def is_cached(self, value):
        """Determines if the specified value is cached. Returns True if it
        is found. Otherwise returns False.
        """
        self._purge()
        return value in self._values

    def clear(self):
        """ Clears all cached values """
        # todo clear all
        self._values = dict()  # Holds the values
        self._time_hash = list()  # Holds the values indexed by time

        self._time_hash = [list() for _ in range(0, self._slice_count)]

    def count(self):
        """Returns the total number of cached objects """
        self._purge()
        return len(self._values)

    def integrity_check(self):
        """Checks internal state of the cache and raises and exception
        if any issue is detected.
        """
        item_count = 0

        for slice_index in range(0, self._slice_count):
            item_count += len(self._time_hash[slice_index])

        if item_count != len(self._values):
            raise FastCacheException("Integrity check failed")

    def _purge(self):
        """Purges all expired values from the cache"""
        self._current_time = int(time())
        self._current_slice = self._timetoslice(self._current_time)

        time_delta = self._current_time - self._last_time

        if time_delta > (self._retention_period - self._slice_size):
            # We wrapped around (all cached values expired)
            self.clear()
        else:

            slice_delta = self._current_slice - self._last_slice

            # Adjust the slice delta for the case where the the last slice's index
            # is greater than the current slice's index.
            if slice_delta < 0:
                slice_delta = self._slice_count + slice_delta

            if slice_delta > 0:
                for x in range(self._last_slice + 1, self._last_slice + slice_delta + 1):
                    s = x % self._slice_count
                    self._clear_slice(s)

        self._last_time = self._current_time
        self._last_slice = self._current_slice

    def _clear_slice(self, slice_index):
        """Clears a time slice with the specified index
        param: slice_index The index of the slice to clear
        """
        delete_count = 0  # Sanity-check

        for item in self._time_hash[slice_index]:
            del self._values[item]
            delete_count += 1

        assert(len(self._time_hash[slice_index]) == delete_count)
        self._time_hash[slice_index] = list()

    def _timetoslice(self, t):
        """Converts specified time to a slice index"""
        return (t // self._slice_size) % self._slice_count
