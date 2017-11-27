#!/usr/bin/env bash

sed -i.bak s/mongo_db_name/$(hostname)/ /etc/rse.conf
cat /etc/rse.conf
gunicorn rse:app -b 0.0.0.0:8000 --log-file - --log-level debug
