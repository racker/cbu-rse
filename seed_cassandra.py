#! /usr/bin/env python

import argparse
import ssl

from cassandra import auth
from cassandra import cluster
from cassandra import policies
from cassandra import query

parser = argparse.ArgumentParser(description="Cassandra token seeder.")
parser.add_argument(
    "--hosts",
    dest="hosts",
    action="store",
    type=str,
    nargs='+',
    help="list of hosts to connect to (e.g. --hosts 127.0.0.1 localhost)"
)
parser.add_argument(
    "--port",
    dest="port",
    action="store",
    type=int,
    default=9042,
    help="cassandra port (default: 9042)"
)
parser.add_argument(
    "--protocol-version",
    dest="protocol",
    action="store",
    type=int,
    default=3,
    choices=[2, 3, 4],
    help=""
)
parser.add_argument(
    "--auth-enabled",
    dest="auth_enabled",
    action="store_true",
    default=False,
    help="requires '--username' and '--password' to be specified"
)
parser.add_argument(
    "--username",
    dest="username",
    action="store",
    default="",
    type=str,
    help="cassandra username"
)
parser.add_argument(
    "--password",
    dest="password",
    action="store",
    default="",
    type=str,
    help="cassandra password"
)
parser.add_argument(
    "--ssl-enabled",
    dest="ssl_enabled",
    action="store_true",
    default=False,
    help="requires '--cert-path'"
)
parser.add_argument(
    "--cert-path",
    dest="ssl_cert_path",
    action="store",
    default="cass.crt",
    type=str,
    help="path to ssl cert for cassandra"
)
parser.add_argument(
    "--num-tokens",
    dest="num_tokens",
    action="store",
    default=1,
    type=int,
    help=(
        "generates integers, 0 .. i .. N where N is the value passed in, and "
        "each token is of the form str(i)"
    )
)
parser.add_argument(
    "--prefix",
    dest="prefix",
    action="store",
    default="QuattroAPI_Login_Ticket_",
    type=str,
    help="auth token prefix"
)
args = parser.parse_args()

auth_provider = None
if args.auth_enabled:
    auth_provider = auth.PlainTextAuthProvider(
        username=args.username,
        password=args.password
    )

ssl_options = None
if args.ssl_enabled:
    ssl_options = {
        "ca_certs": args.ssl_cert_path,
        "ssl_version": ssl.PROTOCOL_TLSv1
    }

print "Connecting to cache"
phx_cluster = cluster.Cluster(
    args.hosts,
    auth_provider=auth_provider,
    load_balancing_policy=policies.RoundRobinPolicy(),
    port=args.port,
    ssl_options=ssl_options,
    protocol_version=args.protocol
)

phx_conn = phx_cluster.connect()
phx_conn.row_factory = query.dict_factory

print "Dropping old keyspace"
try:
    phx_conn.execute(
        """
        DROP KEYSPACE auth_token_cache
        """
    )
except Exception:
    pass

print "Creating keyspace"
phx_conn.execute(
    """
    CREATE KEYSPACE auth_token_cache
    WITH REPLICATION = {'class' : 'SimpleStrategy', 'replication_factor': 1}
    """
)

print "Setting keyspace"
phx_conn.set_keyspace("auth_token_cache")

print "Creating table"
phx_conn.execute(
    """
    CREATE TABLE auth_token_cache (auth_token VARCHAR PRIMARY KEY)
    """
)

print "Populating cache"
for i in range(args.num_tokens):
    phx_conn.execute(
        """
        INSERT INTO auth_token_cache (auth_token)
        VALUES ('{0}')
        """.format(args.prefix + str(i))
    )
