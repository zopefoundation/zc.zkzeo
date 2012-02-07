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
from zope.testing import setupstack
import doctest
import unittest
import manuel.capture
import manuel.doctest
import manuel.testing
import mock
import re
import time
import ZEO.zrpc.connection
import ZODB.config
import zc.monitor
import zc.zk.testing
import zc.zkzeo
import zc.zkzeo.runzeo
import zope.testing.loggingsupport
import zope.testing.renormalizing


def client_exception_when_no_zookeeper_running():
    """If ZooKeeper isn't running, we get an immediate error.

    >>> zc.zkzeo.client('192.0.2.42:2181', '/mydb')
    Traceback (most recent call last):
    ...
    FailedConnect: 192.0.2.42:2181

    >>> ZODB.config.storageFromString('''
    ... %import zc.zkzeo
    ...
    ... <zkzeoclient>
    ...   zookeeper 192.0.2.42:2181
    ...   server /databases/demo
    ...   max-disconnect-poll 1
    ... </zkzeoclient>
    ... ''')
    Traceback (most recent call last):
    ...
    FailedConnect: 192.0.2.42:2181
    """

def server_exception_when_no_zookeeper_running_and_dynamic_port():
    """If ZooKeeper isn't running, we get an immediate error.

    >>> zc.zkzeo.runzeo.test('''
    ...   <zeo>
    ...      address 127.0.0.1
    ...   </zeo>
    ...
    ...   <zookeeper>
    ...      connection 192.0.2.42:2181
    ...      path /databases/demo
    ...   </zookeeper>
    ...
    ...   <filestorage>
    ...      path demo.fs
    ...   </filestorage>
    ... ''', threaded=False)
    Traceback (most recent call last):
    ...
    FailedConnect: 192.0.2.42:2181
    """

def server_session_timeout_setting():
    """
    >>> stop = zc.zkzeo.runzeo.test('''
    ...   <zeo>
    ...      address 127.0.0.1
    ...   </zeo>
    ...
    ...   <zookeeper>
    ...      connection zookeeper.example.com:2181
    ...      path /databases/demo
    ...      session-timeout 4242
    ...   </zookeeper>
    ...
    ...   <filestorage>
    ...      path demo.fs
    ...   </filestorage>
    ... ''')

    >>> import zc.zk
    >>> zk = zc.zk.ZooKeeper('zookeeper.example.com:2181')

    >>> stop.server._ZKServer__zk.recv_timeout()
    4242

    >>> _ = stop()
    """

def client_start_with_empty_addresses():
    """
    >>> handler = zope.testing.loggingsupport.InstalledHandler('zc.zkzeo')

    >>> @zc.thread.Thread
    ... def t1():
    ...     return zc.zkzeo.client('zookeeper.example.com:2181',
    ...                            '/databases/demo', max_disconnect_poll=1)

    >>> @zc.thread.Thread
    ... def t2():
    ...     return ZODB.config.storageFromString('''
    ...     %import zc.zkzeo
    ...     <zkzeoclient>
    ...        zookeeper zookeeper.example.com:2181
    ...        server /databases/demo
    ...        max-disconnect-poll 1
    ...     </zkzeoclient>
    ...     ''')

    Wait a while:

    >>> time.sleep(9)

    At this point, since there aren't any addresses, so both threads are
    still going.

    >>> t1.is_alive(), t2.is_alive()
    (True, True)

    >>> print handler
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>

    >>> handler.clear()

    Now let's start a server:

    >>> stop = zc.zkzeo.runzeo.test(
    ...     '/databases/demo', None, 'zookeeper.example.com:2181')

    And the clients will connect:

    >>> t1.join(9)
    >>> t1.value.is_connected()
    True
    >>> t2.join(9)
    >>> t2.value.is_connected()
    True

    >>> print handler # doctest: +NORMALIZE_WHITESPACE
    zc.zkzeo WARNING
      OK: Got addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      OK: Got addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52814']
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52814']

    >>> handler.uninstall()

    >>> t1.value.close()
    >>> t2.value.close()
    >>> _ = stop()
    """

def client_start_with_empty_addresses_and_no_wait():
    """
    >>> handler = zope.testing.loggingsupport.InstalledHandler('zc.zkzeo')

    >>> c1 = zc.zkzeo.client(
    ...     'zookeeper.example.com:2181', '/databases/demo',
    ...     max_disconnect_poll=1, wait=False)

    >>> c2 = ZODB.config.storageFromString('''
    ...     %import zc.zkzeo
    ...     <zkzeoclient>
    ...        zookeeper zookeeper.example.com:2181
    ...        server /databases/demo
    ...        max-disconnect-poll 1
    ...        wait false
    ...     </zkzeoclient>
    ...     ''')

    Wait a while:

    >>> time.sleep(9)

    At this point, since there aren't any addresses, so both clients are
    disconnected:

    >>> c1.is_connected(), c2.is_connected()
    (False, False)

    >>> print handler
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>

    >>> handler.clear()

    Now let's start a server:

    >>> stop = zc.zkzeo.runzeo.test(
    ...     '/databases/demo', None, 'zookeeper.example.com:2181')

    And the clients will connect:

    >>> wait_until(c1.is_connected)
    >>> wait_until(c2.is_connected)

    >>> print handler # doctest: +NORMALIZE_WHITESPACE
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52814']
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52814']

    >>> handler.uninstall()

    >>> c1.close()
    >>> c2.close()
    >>> _ = stop()
    """

def using_empty_hosts():
    """
    >>> stop = zc.zkzeo.runzeo.test('''
    ...     <zeo>
    ...         address :
    ...     </zeo>
    ...
    ...     <zookeeper>
    ...        connection zookeeper.example.com:2181
    ...        path /databases/demo
    ...     </zookeeper>
    ...
    ...     <filestorage>
    ...        path demo.fs
    ...     </filestorage>
    ...     ''')

    >>> zk = zc.zk.ZooKeeper('zookeeper.example.com:2181')
    >>> zk.print_tree('/databases/demo')
    /demo
      /1.2.3.4:57718
        pid = 8315

    >>> zk.close()
    >>> _ = stop()
    """

def empty_zookeeper_section():
    """
All of the zookeeper section keys should be optional:

    >>> stop = zc.zkzeo.runzeo.test('''
    ...     <zeo>
    ...         address :
    ...     </zeo>
    ...
    ...     <zookeeper>
    ...     </zookeeper>
    ...
    ...     <filestorage>
    ...        path demo.fs
    ...     </filestorage>
    ...     ''')

    >>> _ = stop()


    """

def setUp(test):
    setupstack.setUpDirectory(test)
    zc.zk.testing.setUp(test, tree='/databases\n  /demo\n')

    # The original server loop spews thread exceptions during shutdowm.
    # This version doesn't.
    from ZEO.zrpc.connection import server_loop as _server_loop
    def server_loop(map):
        try:
            _server_loop(map)
        except Exception:
            if len(map) > 1:
                raise

    setupstack.context_manager(
        test, mock.patch('ZEO.zrpc.connection.server_loop')
        ).side_effect = server_loop

    setupstack.context_manager(
        test, mock.patch('netifaces.interfaces')).return_value = ['iface']
    setupstack.context_manager(
        test, mock.patch('netifaces.ifaddresses')).return_value = {
        2: [dict(addr='1.2.3.4')]}

def tearDown(test):
    zc.zk.testing.tearDown(test)
    setupstack.tearDown(test)

def tearDownREADME(test):
    tearDown(test)
    zc.monitor.last_listener.close()

def test_suite():
    checker = zope.testing.renormalizing.RENormalizing([
        (re.compile(r'pid = \d+'), 'pid = PID'),
        (re.compile(r'127.0.0.1:\d+'), '127.0.0.1:PORT'),
        (re.compile(r'1.2.3.4:\d+'), '1.2.3.4:PORT'),
        (re.compile(r'localhost:\d+'), 'localhost:PORT'),
        ])
    suite = unittest.TestSuite((
        doctest.DocTestSuite(
            setUp=setUp, tearDown=tearDown, checker=checker),
        manuel.testing.TestSuite(
            manuel.doctest.Manuel(checker=checker) + manuel.capture.Manuel(),
            'README.txt',
            setUp=setUp, tearDown=tearDownREADME,
            ),
        ))
    if not zc.zk.testing.testing_with_real_zookeeper():
        suite.addTest(doctest.DocFileSuite(
            'wait-for-zookeeper.test',
            setUp=setUp, tearDown=tearDown,
            checker=checker))

    return suite

