# Really Simple Events

Reference implementation for Really Simple Events, a simple event queueing protocol inspired by RSS.

Currently in production supporting Rackspace Cloud Backup.

RSE is a light-weight, fast, scale-out alternative to other popular queueing systems. It is a good choice when you need a cloud message bus that supports 100's of thousands of clients, and was specifically designed for communicating across unreliable network partitions (read: the internet). Unlike simple timestamp-based protocols, RSE guarantees clients will never miss an event due to clock drift or ID collisions, while at the same time clients do not have to keep a sliding window of previously received events to detect duplicates.

## Features

* Supports events and command-and-control symantics
* Clients communicate over channels and sub-channels
* Designed in an elegant fashion so that communication styles are only limited by your imagination (point-to-point and publish-subscribe are emergent features, not hard-wired into the protocol)  
* Uses a simple, compact, and human-readable HTTP+JSON protocol
* Plays nice with standard web servers, firewalls, routers, proxies, etc.
* Stateless app servers with high utilization
* Does not require long-lived connections
* Low-latency polling 
* Supports keep-alive for percieved real-time command and control

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

## Coming soon

* Modular design (storage driver, auth, etc.)
* Improved scale-out for writes
* Transactional symantecs (to support job queues)
* ...and much more!