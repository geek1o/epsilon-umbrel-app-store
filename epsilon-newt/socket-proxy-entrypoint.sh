#!/bin/sh
set -eu

mkdir -p /run/haproxy /proxy
rm -f /proxy/docker.sock
sed 's|@@BIND_PROTO@@|/proxy/docker.sock mode 0666|' /templates/haproxy.cfg > /run/haproxy/haproxy.cfg

exec /usr/sbin/haproxy -f /run/haproxy/haproxy.cfg -W -db
