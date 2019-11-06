from setuptools import setup, find_packages

# It's annoying to track dependencies inline with install_requires
dependencies = [
    "moecache>=1,<2",
    "pymongo>=3,<4",
    "webob",
    "pyyaml",
    "tenacity",
    "setuptools",
]

scm_version_options = {
        'write_to': 'src/rse/version.py',
        'fallback_version': 'UNKNOWN',
        }

setup(
    name="rse",
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
    include_package_data=True,
    install_requires=dependencies,
    setup_requires=['setuptools_scm'],
    use_scm_version=scm_version_options,
    tests_require=['tox'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'rse = rse.cli:main'
        ]
    },
)
