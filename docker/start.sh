#!/bin/bash

service nginx restart
rse --versions | column -t
rse --debug
