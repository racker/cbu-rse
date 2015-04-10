import abc
import ssl
import time
import uuid

from cassandra import auth
from cassandra import cluster
from cassandra import policies
from cassandra import query
import moecache
import six


@six.add_metaclass(abc.ABCMeta)
class AuthCacheBase(object):
    def __init__(self, config, logger):
        self.prefix = config.get('authcache', 'authtoken-prefix')
        self.logger = logger

    def get(self, token):
        """Retrieve token from cache."""
        raise NotImplementedError

    def set(self, token):
        """Set token in cache."""
        raise NotImplementedError

    def auth(self, token):
        """Check if token exists."""
        if self.get(token) is not None:
            return True
        else:
            return False

    def connected(self):
        """Check that we can successfully set and get a token."""
        key = str(uuid.uuid4())
        self.set(key)
        return self.auth(key)


class CassandraAuthCache(AuthCacheBase):
    def __init__(self, config, logger):
        super(CassandraAuthCache, self).__init__(config, logger)
        raw_cluster = config.get("cassandra", "cluster")
        cluster_ips = [addr for addr in raw_cluster.split(',')]
        self.keyspace = config.get("cassandra", "keyspace")

        port = config.getint("cassandra", "port")

        if config.getboolean("cassandra", "ssl_enabled"):
            cert_path = config.get("cassandra", "ssl_ca_certs")
            ssl_options = {
                'ca_certs': cert_path,
                'ssl_version': ssl.PROTOCOL_TLSv1
            }
        else:
            ssl_options = None

        if config.getboolean("cassandra", "auth_enabled"):
            username = config.get("cassandra", "username")
            password = config.get("cassandra", "password")

            auth_provider = auth_provider = auth.PlainTextAuthProvider(
                username=username,
                password=password
            )
        else:
            auth_provider = None

        load_balance_strategy = config.get(
            "cassandra",
            "load_balance_strategy"
        )
        load_balancing_policy_class = getattr(policies, load_balance_strategy)
        if load_balancing_policy_class is policies.DCAwareRoundRobinPolicy:
            datacenter = config.get("cassandra", "datacenter")
            load_balancing_policy = load_balancing_policy_class(datacenter)
        else:
            load_balancing_policy = load_balancing_policy_class()

        self.cassandra_cluster = cluster.Cluster(
            cluster_ips,
            auth_provider=auth_provider,
            load_balancing_policy=load_balancing_policy,
            port=port,
            ssl_options=ssl_options
        )

        # In case cassandra is not up prior to running RSE, retry every 5 sec
        connected = False
        while not connected:
            try:
                self.session = self.cassandra_cluster.connect()
                connected = True
            except Exception:
                time.sleep(5)

        self.session.row_factory = query.dict_factory

    def get(self, token):
        # TODO(Kuwagata) Add consistency failover
        rows = self.session.execute(
            """SELECT * FROM {0}.auth_token_cache WHERE api_key = %(token)s
            """.format(self.keyspace),
            {
                "token": (self.prefix + token),
            }
        )
        if len(rows) > 0:
            self.logger.debug("CASSANDRA GET: " + str(rows))
            return rows
        else:
            return None

    def set(self, token):
        self.session.execute(
            """INSERT INTO {0}.auth_token_cache
            (
                api_key
            )
            VALUES
            (
                %(token)s
            )
            """.format(self.keyspace),
            {
                "token": (self.prefix + token),
            }
        )


class MemcachedAuthCache(AuthCacheBase):
    def __init__(self, config, logger):
        super(MemcachedAuthCache, self).__init__(config, logger)

        raw_shards = config.get('memcached', 'memcached-shards')
        timeout = config.getint('memcached', 'memcached-timeout')

        shards = [
            (host, int(port))
            for host, port in
            [
                addr.split(':')
                for addr in
                raw_shards.split(',')
            ]
        ]

        self.client = moecache.Client(
            shards,
            timeout=timeout
        )

    def get(self, token):
        return self.client.get(token)

    def set(self, token):
        # ttl is unconfigured since set is only used for online status
        self.client.set(token, 1, 60)
