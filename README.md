# Really Simple Events

Reference implementation for Really Simple Events, a simple event queueing protocol inspired by RSS.

Currently in production supporting Rackspace Cloud Backup.

RSE is a light-weight, fast, scale-out alternative to other popular queueing systems. It is a good choice when you need a cloud message bus that supports 100's of thousands of clients, and was specifically designed for communicating across unreliable network partitions (read: the internet).

Unlike simple timestamp-based protocols, RSE guarantees clients will never miss an event due to clock drift or ID collisions, while at the same time clients do not have to keep a sliding window of previously received events to detect duplicates.

## Quick Start

#### Local install
1. Install MongoDB 2.2.
1. Install Python 2.7. On Windows, you'll have to manually add it to your path (probably c:\python27\bin).
1. ```pip install pymongo webob```
1. Clone rse
1. Cd into the directory, then run: ```init_repo.sh``` to download the `rse-util` submodule.
1. Cd into the `rse-util` sub-directory, then run: ```pip install -e .```
1. Return to the parent directory, then run: ```python rse.py```
1. If that doesn't work, check ```rse.log``` for errors.

###### Note

One can also clone the rse-util repository (https://github.com/rackerlabs/rse-util) separately and install is as opposed to using `init_repo.sh` to utilize `git submodule`s.

#### Docker install
1. `cd rse`
1. `cp rse.docker.template.conf rse.docker.conf` and modify configuration options as needed (currently, that's just `auth_url` in the `[eom:auth]` section).
1. Run `./init_repo.sh` in order to initialize the `git submodule` for `rse-util`.
1. docker-compose build
1. docker-compose up -d

## Features

* Clients communicate over channels and sub-channels
* Supports both eventing and command-and-control semantics
* Designed in an elegant fashion so that communication styles are only limited by your imagination (point-to-point and pubsub are emergent features, not hard-wired into the protocol)  
* Uses a simple, compact, and human-readable HTTP+JSON protocol
* Plays nice with standard web servers, firewalls, routers, proxies, etc.
* Stateless app servers with high utilization
* Does not require long-lived connections
* Low-latency polling of ~8 ms (combine with keep-alive for [perceptually instantaneous][1] command and control)
* Guaranteed delivery of events (within a specific time window)

## Configuration

```
cp rse.default.conf /etc/rse.conf
vim /etc/rse.conf
```

## RSE Dependencies

* Python 2 (2.6 or better)
* WebOb
* Gunicorn
* Pymongo
* [Rse-Util][2] (formerly RaxPy)

## Reference Stack

* Nginx
* Gunicorn => rse.py
* MongoDB
* Linux (CentOS, RHEL or Ubuntu)

## Coming soon

* Modular design (storage driver, auth, etc.)
* Improved scale-out for writes
* Transactional semantics (to support job queues)
* ...and much more!

[1]:http://asktog.com/basics/firstPrinciples.html#latencyReduction
[2]:https://github.com/rackerlabs/rse-util
