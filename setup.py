from setuptools import setup, find_packages

setup(
    name="rse",
    version="2.1.0",
    packages = find_packages(),
    description="Real Simple Events",
    url="https://github.com/rackerlabs/rse/",
    maintainer="ATL Devops",
    maintainer_email="devops.atl@lists.rackspace.com",
    classifiers=["Private :: Do Not Upload"],
    install_requires=["eom>=0.8.0", "pymongo<3", "webob"],
    py_modules=["rse", "json_validator", "rseutils"]
)
