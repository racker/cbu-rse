#!/bin/bash

is_ready() {
    nc -z cache 9042
}

# wait until cassandra is ready
while ! is_ready -eq 1
do
  echo "$(date) - still trying to connect to cassandra"
  sleep 1
done
echo "$(date) - connected successfully to cassandra"

echo "Seeding cassandra with token"
seed_cassandra --hosts cache

# start RSE
cd /home/rse
echo "Starting RSE"
exec gunicorn rse:app -b 0.0.0.0:8000 --log-file - --log-level debug
