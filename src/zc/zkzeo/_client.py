##############################################################################
#
# Copyright (c) Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
import logging
import time
import zc.zk
import ZEO.ClientStorage
import threading

logger = logging.getLogger('zc.zkzeo')

def client(zkaddr, path, *args, **kw):
    zk = zc.zk.ZooKeeper(zkaddr)
    addresses = zk.children(path)
    wait = kw.get('wait', kw.get('wait_for_server_on_startup', True))
    client = ZEO.ClientStorage.ClientStorage(
        _wait_addresses(addresses, parse_addr, zkaddr, path, wait),
        *args, **kw)
    return _client(addresses, client, zkaddr, path)

def parse_addr(addr):
    host, port = addr.split(':')
    return host, int(port)

def _client(addresses, client, zkaddr, path):

    new_addr = getattr(client, 'new_addr', None)
    if new_addr is None:
        # Pre 3.11 client.  We need to make our own new_addr.
        # This is ugly. Don't look. :(
        def new_addr(addr):
            manager = client._rpc_mgr
            manager.addrlist = manager._parse_addrs(addr)
            with manager.cond:
                if manager.thread is not None:
                    manager.thread.addrlist = manager.addrlist

    warned = set()

    @addresses
    def changed(addresses):
        addrs = map(parse_addr, addresses)
        if addrs:
            if warned:
                logger.warning('OK: Addresses from <%s%s>', zkaddr, path)
                warned.clear()
            logger.info('Addresses from <%s%s>: %r',
                        zkaddr, path, sorted(addresses))
        else:
            logger.warning('No addresses from <%s%s>', zkaddr, path)
            warned.add(1)
        new_addr(addrs)

    client.zookeeper_addresses = addresses

    return client

def _wait_addresses(addresses, transform, zkaddr, path, wait):
    n = 0
    while 1:
        result = [transform(addr) for addr in addresses]
        if result:
            if n:
                logger.warning("OK: Got addresses from <%s%s>",
                               zkaddr, path)
            return result
        if not wait:
            return result
        if (n%30000) == 0: # warn every few minutes
            logger.warning("No addresses from <%s%s>", zkaddr, path)
        time.sleep(.01)
        n += 1

class ZConfig:

    def __init__(self, config):
        self.config = config
        self.name = config.getSectionName()

    def open(self):
        import ZConfig.datatypes
        import ZODB.config

        zkaddr = self.config.zookeeper
        zk = zc.zk.ZooKeeper(zkaddr)
        paths = [server.address for server in self.config.server]
        if len(paths) > 1:
            raise TypeError("Only one server option is allowed")
        path = paths[0]
        if not isinstance(path, basestring) or not path[0] == '/':
            raise TypeError("server must be a ZooKeeper path, %r" % path)
        addresses = zk.children(path)
        self.config.server = _wait_addresses(
            addresses, ZConfig.datatypes.SocketAddress,
            zkaddr, path, self.config.wait)

        client = ZODB.config.ZEOClient(self.config).open()
        return _client(addresses, client, zkaddr, path)
