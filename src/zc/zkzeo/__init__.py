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

def client(zookeeper_connection_string, path, *args, **kw):
    import zc.zkzeo._client
    return zc.zkzeo._client.client(zookeeper_connection_string, path,
                                   *args, **kw)

def DB(zookeeper_connection_string, path, *args, **kw):
    import ZODB
    return ZODB.DB(client(zookeeper_connection_string, path, *args, **kw))

def connection(zookeeper_connection_string, path, *args, **kw):
    db = DB(zookeeper_connection_string, path, *args, **kw)
    conn = db.open()
    conn.onCloseCallback(db.close)
    return conn
