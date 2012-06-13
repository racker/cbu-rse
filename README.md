# Really Simple Events

Reference implementation for Really Simple Events, a simple event queueing protocol inspired by RSS.

Currently used in Rackspace Cloud Backup.

RSE is a light-weight, fast, scale-out alternative to other popular queueing systems, and was specifically designed for communicating across unreliable network partitions (read: the internet). Unlike simple timestamp-based protocols, RSE guarantees clients will never miss an event due to clock drift or ID collisions, while at the same time clients do not have to keep a sliding window of previously received events to detect duplicates.

## RSE Dependencies

* Python 2 (2.6 or better)
* WebOb
* Gunicorn
* Pymongo
* [RaxPy](https://github.rackspace.com/atl/rax-py)

## Reference Stack

* Nginx
* Gunicorn => rse.py
* MongoDB
* Linux (CentOS, RHEL or Ubuntu)