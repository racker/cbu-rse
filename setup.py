from setuptools import setup, find_packages

# It's annoying to track dependencies inline with install_requires
dependencies = [
    "eom>=0.8.0",
    "pymongo<3",
    "webob",
]
version = "2.2.0"  # NOTE: Makefile greps for this line.

setup(
    name="rse",
    version=version,
    description="Real Simple Events",
    url="https://github.com/rackerlabs/rse/",
    classifiers=["Private :: Do Not Upload"],
    maintainer="ATL Devops",
    maintainer_email="devops.atl@lists.rackspace.com",
    packages=find_packages(exclude=['tests*', 'rse/tests']),
    install_requires=dependencies,
    tests_require=['tox'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'dev-rse = rse.cmd:main'
        ]
    },
)
