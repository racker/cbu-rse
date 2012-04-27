# Really Simple Events

Here's the official reference implementation for Really Simple Events, a simple event queueing protocol inspired by RSS. RSE is a light-weight, fast, scale-out alternative to other popular queueing systems, and was specifically designed for communicating across unreliable network partitions (read: the internet). Unlike simple timestamp-based protocols, RSE guarantees clients will never miss an event due to clock drift or ID collisions. 

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

## Roadmap Brainstorm

* Migrate documentation. roadmap to GitHub wiki and/or README.md
* Move this list to the wiki!
* Document "events" parameter 
* API doc generator
* Improve code documentation in general
* Create a test suite
* Consider open-sourcing the protocol and a reference implementation
* StatsD integration
* More failure-resistant /health?verbose (build up report as we go, return as much as we can)
* PyPy support
* Add Push support for highly latency-sensitive use cases (e.g., real-time user interfaces)
* Final benchmarking and scalability analysis for polling mode (initial results show sustained 7-9K reqs/sec, mixed GETs and POSTs with authentication, per node)
* Modify ID generation logic/last-known-id semantics to allow scaling out writes
* Investigate use of Node.js to further improve node utilization and reduce latency
* Compare/contrast Paste with RaxPy in terms of useability and performance
* Benchmark Apache 2.4 + event MPM vs current Nginx + gunicorn stack
* Contribute a TTL feature to MongoDB to remove the need for gc.py
* Add support for request signing