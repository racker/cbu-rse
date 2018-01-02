from setuptools import setup, find_packages

# It's annoying to track dependencies inline with install_requires
dependencies = [
    "eom>=0.8.2",
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
    # The exclude below is a bit of prophylactic. If someone puts a tests dir
    # under src in future, it won't get included in the package (note: don't do
    # that).
    packages=find_packages("src", exclude=['tests*', 'rse/tests']),
    package_dir={'': "src"},
    install_requires=dependencies,
    tests_require=['tox'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'dev-rse = rse.cmd:main'
        ]
    },
)
