from setuptools import setup, find_packages
from glob import glob

setup(
    name = "rse",
    version = "2.0.0",
    description = "Real Simple Events",
    url = "https://github.com/rackerlabs/rse/",
    maintainer = "ATL Devops",
    maintainer_email = "devops.atl@lists.rackspace.com",
    classifiers = ["Private :: Do Not Upload"],
    install_requires = ["pymongo", "rax", "moecache", "cassandra-driver"],
    packages = ["controllers"],
    py_modules = ["rse", "json_validator", "auth_cache", "rseutils"]
)
