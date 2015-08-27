import abc
import ssl
import time
import uuid

import cassandra
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
        self.default_ttl = config.getint('authcache', 'default_ttl')
        self.logger = logger

    def get(self, token):
        """Retrieve token from cache."""
        raise NotImplementedError

    def set(self, token, ttl=None):
        """Set token in cache."""
        raise NotImplementedError

    def auth(self, token):
        """Check if token exists."""
        return self.get(token) is not None

    def connected(self):
        """Check that we can successfully set and get a token."""
        key = str(uuid.uuid4())
        self.set(key)
        return self.auth(key)

    def _get_ttl(self, ttl):
        if ttl is None:
            return self.default_ttl
        else:
            try:
                return int(ttl)
            except ValueError:
                raise ValueError("invalid integer for ttl: {0}".format(ttl))


class CassandraAuthCache(AuthCacheBase):
    def __init__(self, config, logger):
        super(CassandraAuthCache, self).__init__(config, logger)
        raw_cluster = config.get("cassandra", "cluster")
        cluster_ips = [addr for addr in raw_cluster.split(',')]
        self.keyspace = config.get("cassandra", "keyspace")
        max_connect_retries = config.getint("cassandra", "max_retries")

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

            auth_provider = auth.PlainTextAuthProvider(
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
            ssl_options=ssl_options,
            protocol_version=int(
                config.get("cassandra", "protocol_version", 3)
            )
        )

        # In case cassandra is not up prior to running RSE, retry every 5 sec
        for i in range(max_connect_retries):
            try:
                self.session = self.cassandra_cluster.connect()
            except Exception:
                time.sleep(5)

        self.session.row_factory = query.dict_factory

    def get(self, token):
        select_statement = """SELECT *
            FROM {0}.auth_token_cache
            WHERE auth_token = %(auth_token)s
        """.format(self.keyspace)

        args = {
            "auth_token": (self.prefix + token),
        }

        try:
            rows = self.session.execute(
                query.SimpleStatement(
                    select_statement,
                    consistency_level=cassandra.ConsistencyLevel.LOCAL_ONE
                ),
                args
            )
        except Exception:
            try:
                rows = self.session.execute(
                    query.SimpleStatement(
                        select_statement,
                        consistency_level=(
                            cassandra.ConsistencyLevel.LOCAL_QUORUM
                        )
                    ),
                    args
                )
            except Exception:
                self.logger.exception(
                    "Failover to LOCAL_QUORUM failed for %s",
                    args["token"]
                )
                raise
        if len(rows) > 0:
            return rows
        else:
            return None

    def set(self, token, ttl=None):
        insert_statement = query.SimpleStatement(
            """INSERT INTO {0}.auth_token_cache
            (
                auth_token
            )
            VALUES
            (
                %(auth_token)s
            )
            USING TTL %(ttl)s
            """
        )

        self.session.execute(
            insert_statement,
            {
                "auth_token": (self.prefix + token),
                "ttl": self._get_ttl(ttl),
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
        return self.client.get(self.prefix + token)

    def set(self, token, ttl=None):
        self.client.set(self.prefix + token, 1, self._get_ttl(ttl))
