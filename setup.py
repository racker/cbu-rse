from setuptools import setup

setup(
    name="rse",
    version="2.0.2",
    description="Real Simple Events",
    url="https://github.com/rackerlabs/rse/",
    maintainer="ATL Devops",
    maintainer_email="devops.atl@lists.rackspace.com",
    classifiers=["Private :: Do Not Upload"],
    install_requires=["rax", "eom>=0.8.0", "pymongo<3"],
    packages=["controllers"],
    py_modules=["rse", "json_validator", "rseutils"]
)
