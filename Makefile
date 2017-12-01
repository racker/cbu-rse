# This is just for convenience.

.PHONY : all wheel venv clean

pyfiles = $(shell find src -type f -name '*.py')
# Probably breaks if the version is an alpha/beta or something.
version = $(shell grep ^version setup.py | grep -oh '[0-9].*\.[0-9].*\.[0-9]')
wheel = rse-$(version)-py2-none-any.whl

all : wheel
wheel : dist/$(wheel)

dist/$(wheel) : $(pyfiles)
	python setup.py bdist_wheel

venv : wheel
	virtualenv venv; . venv/bin/activate; pip install dist/$(wheel); deactivate

clean :
	-rm -rf build dist venv *.egg-info
