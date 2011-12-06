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
import time
import zc.zk
import ZEO.ClientStorage
import threading

def client(zk, path, *args, **kw):
    zk = zc.zk.ZooKeeper(zk)
    addresses = zk.children(path)
    client = ZEO.ClientStorage.ClientStorage(
        _wait_addresses(addresses, parse_addr),
        *args, **kw)
    return _client(addresses, client)

def DB(*args, **kw):
    import ZODB
    return ZODB.DB(client(*args, **kw))

def connection(*args, **kw):
    return DB(*args, **kw).open_once()

def parse_addr(addr):
    host, port = addr.split(':')
    return host, int(port)

def _client(addresses, client):

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

    @addresses
    def changed(addresses):
        addrs = map(parse_addr, addresses)
        if addrs:
            new_addr(addrs)

    client.zookeeper_addresses = addresses

    return client

def _wait_addresses(addresses, transform):
    while 1:
        result = [transform(addr) for addr in addresses]
        if result:
            return result
        time.sleep(1)

class ZConfig:

    def __init__(self, config):
        self.config = config
        self.name = config.getSectionName()

    def open(self):
        import ZConfig.datatypes
        import ZODB.config

        zk = zc.zk.ZooKeeper(self.config.zookeeper)
        paths = [server.address for server in self.config.server]
        if len(paths) > 1:
            raise TypeError("Only one server option is allowed")
        path = paths[0]
        if not isinstance(path, basestring) or not path[0] == '/':
            raise TypeError("server must be a ZooKeeper path, %r" % path)
        addresses = zk.children(path)
        self.config.server = _wait_addresses(
            addresses, ZConfig.datatypes.SocketAddress)

        client = ZODB.config.ZEOClient(self.config).open()
        return _client(addresses, client)
