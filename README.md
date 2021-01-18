# Really Simple Events

Reference implementation for Really Simple Events, a simple event
queueing protocol inspired by RSS.

Currently in production supporting Rackspace Cloud Backup.

RSE is a light-weight, fast, scale-out alternative to other popular
queueing systems. It is a good choice when you need a cloud message bus
that supports 100's of thousands of clients, and was specifically
designed for communicating across unreliable network partitions (read:
the internet).

Unlike simple timestamp-based protocols, RSE guarantees clients will
never miss an event due to clock drift or ID collisions, while at the
same time clients do not have to keep a sliding window of previously
received events to detect duplicates.

## Installation

1. Install Python 3. On Windows, you'll have to manually add it to
   your path (probably `c:\python3\bin`).
1. Clone this repository.
1. `pip install .`

That's it. When developing, you may want to add pip's `--editable`
switch.

### Docker Installation

1. Clone this repository.
1. `docker-compose build`
1. `docker-compose up`

RSE will listen on local port 8000; you can test that it is running with
`curl http://localhost:8000/health` or similar. The response body will
read "OK".

## Features

* Clients communicate over channels and sub-channels
* Supports both eventing and command-and-control semantics
* Designed in an elegant fashion so that communication styles are only
  limited by your imagination (point-to-point and pubsub are emergent
  features, not hard-wired into the protocol)  
* Uses a simple, compact, and human-readable HTTP+JSON protocol
* Plays nice with standard web servers, firewalls, routers, proxies,
  etc.
* Stateless app servers with high utilization
* Does not require long-lived connections
* Low-latency polling of ~8 ms (combine with keep-alive for
  [perceptually instantaneous][1] command and control)
* Guaranteed delivery of events (within a specific time window)

## Configuration

RSE has two config files, `rse.yaml` and `logging.yaml`. The defaults
for both are visible under `src/rse/config`, along with suggested usage.
On startup, RSE looks for them at the following locations:

- `$RSE_CONF_DIR`, if set.
- `~/.config/rse`
- `/etc/rse`

The first one found is used. Values in the config files override the
defaults. You do not need to re-provide the defaults. Hence most RSE
deployments can have very small conf files.

## Dependencies

Python 3 is the only system-level dependency. All others are brought in
via pip during installation. See `setup.py` for the complete list.

RSE relies on `memcached` (for auth token verification) and `mongodb`
(for event storage).

We suggest `gunicorn` as a WSGI server. The WSGI application path is
`rse.wsgi:app`. RSE is capable of self-running, but it's not recommended
in production. If you do need to self-run it, `rse --help` will list the
available options.

`nginx` or a similar web server should run in front. There's a sample
configuration under `docker/nginx.rse.conf`.

RSE is typically deployed on Ubuntu, but theoretically can run on any
system with an appropriate Python.

## Updating Socket Limits

The maximum number of open file descriptors usually needs to be bumped early on.
Unix/Linux-based OSes treat sockets as if they were files.

```bash
$ sudo ulimit -n 4096
```

The maximum socket backlog can also be increased. Listening sockets have an
associated queue of incoming connections that are waiting to be accepted.
If you happen to have a stampede of clients that fill up this queue new
connections will eventually start getting dropped.

```bash
$ sudo sysctl -w net.core.somaxconn="4096"
```

## Other Documentation

* [RSE Developer Guide](https://github.com/racker/cbu-rse/blob/development/doc/README.md)
* [RSE Example Data Flow](https://github.com/racker/cbu-rse/blob/development/doc/example-data-flow.pdf)

[1]: http://asktog.com/basics/firstPrinciples.html#latencyReduction
