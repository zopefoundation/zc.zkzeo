from __future__ import print_function
##############################################################################
#
# Copyright (c) 2011 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""%prog [options] zookeeper path

Where:

  zookeeper
    A ZooKeeper connection string

  path
    A ZooKeeper path at which to look up a ZEO server
"""
import json
import optparse
import os
import re
import socket
import struct
import sys
import time
import zc.zk
import ZEO.nagios

zc_monitor_help = """zc.monitor server address to use to look up a server

When multiple servers are are registered at a ZooKeeper path, we need
to know which one to monitor. If a zkzeo server was condigured with a
monitor server, we can connect to the monitor server to determine the
address to monitor.

"""

def connect(addr):
    m = re.match(r'\[(\S+)\]:(\d+)$', addr)
    if m:
        addr = m.group(1), int(m.group(2))
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        m = re.match(r'(\S+):(\d+)$', addr)
        if m:
            addr = m.group(1), int(m.group(2))
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    s.connect(addr)
    fp = s.makefile()
    return fp, s

def find_server(zookeeper, path, monitor_address):
    server = None
    if monitor_address:
        try:
            fp, s = connect(monitor_address)
        except socket.error as err:
            return print("Can't connect %s" % err)

        s.settimeout(1.0)
        fp.write('servers %s\n' % path)
        fp.flush()
        data = fp.read().strip()
        fp.close(); s.close()
        if data.lower().startswith("invalid "):
            return print(data + ' at %r' % monitor_address)
        servers = list(set(data.split())) # dedup
        if not servers:
            return print("No servers at: %r" % monitor_address)
        if len(servers) > 1:
            return print("Too many servers, %r, at: %r" %
                         (sorted(servers), monitor_address))
        server = servers[0]

    zk = zc.zk.ZK(zookeeper)
    children = zk.get_children(path)
    zk.close()
    if server:
        host, port = server.split(':')
        if host:
            children = [c for c in children if c == server]
        else:
            children = [c for c in children if c.split(':')[1] == port]

    if len(children) != 1:
        return print("Couldn't find server in ZooKeeper")
    addr = children[0]
    return addr

def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = optparse.OptionParser(__doc__)
    parser.add_option(
        '-m', '--output-metrics', action="store_true",
        help="Output metrics.",
        )
    parser.add_option(
        '-s', '--status-path',
        help="Path to status file, needed to get rate metrics",
        )
    parser.add_option(
        '-u', '--time-units', type='choice', default='minutes',
        choices=['seconds', 'minutes', 'hours', 'days'],
        help="Time unit for rate metrics",
        )
    parser.add_option('-M', '--zc-monitor-address', help=zc_monitor_help)
    (options, args) = parser.parse_args(args)
    [zk, path] = args

    addr = find_server(zk, path, options.zc_monitor_address)
    if not addr:
        return 2

    return ZEO.nagios.check(
        addr, options.output_metrics, options.status_path, options.time_units)
