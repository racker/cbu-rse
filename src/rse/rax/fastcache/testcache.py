#!/usr/bin/env python

"""
Fastcache unit tests
"""

import unittest
from time import sleep, time
from .fastcache import FastCache
from random import random


class TestCache(unittest.TestCase):

    def setUp(self):
        self.c = FastCache(retention_period=12, slice_size=1)

    def test_basic(self):
        value = "myvalue"
        self.c.cache(value)
        self.assertTrue(self.c.is_cached(value))
        self.assertFalse(self.c.is_cached("bogus value"))
        sleep(12.1)
        self.assertFalse(self.c.is_cached(value))

    def test_many_values(self):
        for x in range(1, 1000000):
            self.c.cache(str(x))
            self.assertTrue(self.c.is_cached(str(x)))
            self.assertFalse(self.c.is_cached(str(x + 1)))

        self.c.integrity_check()

        # Now insert some more random values....

        start_time = time()

        x = 0

        while time() - start_time < 12:
            self.c.cache('distractor ' + str(x))
            x += 1

        self.c.integrity_check()

        # Now all of the original values should have been removed.
        for x in range(1, 1000000):
            self.assertFalse(self.c.is_cached(str(x)))

        self.c.integrity_check()

        start_time = time()
        x = 0

        while time() - start_time < 12:
            bogus = "really long bogus value that doesn't really exist"
            self.assertFalse(self.c.is_cached(bogus))
            x += 1

        self.assertEqual(self.c.count(), 0)


if __name__ == '__main__':
    unittest.main()
