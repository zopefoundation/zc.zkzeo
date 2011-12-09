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
import doctest
import unittest
import manuel.capture
import manuel.doctest
import manuel.testing
import mock
import re
import ZEO.zrpc.connection
import zc.zk.testing
import zc.zkzeo
import zope.testing.setupstack
import zope.testing.renormalizing


def client_exception_when_no_zookeeper_running():
    """If ZooKeeper isn't running, we get an immediate error.

    >>> zc.zkzeo.client('192.0.2.42:2181', '/mydb')
    Traceback (most recent call last):
    ...
    FailedConnect: 192.0.2.42:2181

    >>> import ZODB.config
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

    >>> import zc.zkzeo.runzeo
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
    >>> import zc.zkzeo.runzeo
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


def setUp(test):
    zc.zk.testing.setUp(test, tree='/databases\n  /demo\n')
    test.globs['_server_loop'] = _server_loop = ZEO.zrpc.connection.server_loop

    # The original server loop spews thread exceptions during shutdowm.
    # This version doesn't.
    def server_loop(map):
        try:
            _server_loop(map)
        except Exception:
            if len(map) > 1:
                raise

    ZEO.zrpc.connection.server_loop = server_loop

def tearDown(test):
    zc.zk.testing.tearDown(test)
    ZEO.zrpc.connection.server_loop = test.globs['_server_loop']

def test_suite():
    checker = zope.testing.renormalizing.RENormalizing([
        (re.compile(r'pid = \d+'), 'pid = PID'),
        (re.compile(r'/127.0.0.1:\d+'), '/127.0.0.1:PORT'),
        ])
    suite = unittest.TestSuite((
        doctest.DocTestSuite(
            setUp=setUp, tearDown=zc.zk.testing.tearDown,
            ),
        manuel.testing.TestSuite(
            manuel.doctest.Manuel(checker=checker) + manuel.capture.Manuel(),
            'README.txt',
            setUp=setUp, tearDown=zc.zk.testing.tearDown,
            ),
        ))
    if not zc.zk.testing.testing_with_real_zookeeper():
        suite.addTest(doctest.DocFileSuite(
            'wait-for-zookeeper.test',
            setUp=setUp, tearDown=zc.zk.testing.tearDown,
            checker=checker))

    return suite

