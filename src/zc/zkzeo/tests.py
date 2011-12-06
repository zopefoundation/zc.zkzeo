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
import zope.testing.setupstack
import zope.testing.renormalizing

def setUp(test):
    zc.zk.testing.setUp(test, tree='/databases\n  /demo\n')
    test.globs['_server_loop'] = ZEO.zrpc.connection.server_loop

    # The original server loop spews thread exceptions during shutdowm.
    # This version doesn't.
    def server_loop(map):
        try:
            test.globs['_server_loop'](map)
        except Exception:
            if len(map) > 1:
                raise

    ZEO.zrpc.connection.server_loop = server_loop

def tearDown(test):
    zc.zk.testing.tearDown(test)
    ZEO.zrpc.connection.server_loop = test.globs['_server_loop']

def test_suite():
    return unittest.TestSuite((
        # doctest.DocFileSuite('README.test'),
        # doctest.DocTestSuite(),
        manuel.testing.TestSuite(
            manuel.doctest.Manuel(
                checker = zope.testing.renormalizing.RENormalizing([
                    (re.compile(r'pid = \d+'), 'pid = PID'),
                    (re.compile(r'/127.0.0.1:\d+'), '/127.0.0.1:PORT'),
                    ])
                ) + manuel.capture.Manuel(),
            'README.txt',
            setUp=setUp, tearDown=zc.zk.testing.tearDown,
            ),
        ))

