=============
ZEO ZooKeeper
=============

Managing addresses, and especially ports is a drag.  ZooKeeper can be
used as a service registry.  Servers can register themselves and
clients can find services there.  The ``zc.zkzeo`` package provides
support for registering ZEO servers and a ZEO client storage that gets
addresses from ZooKeeper.

.. contents::

Running ZEO servers
===================

To run a ZEO server, and register it with ZooKeeper, first create a
ZEO configuration file::

   <zeo>
      address 127.0.0.1
   </zeo>

   <zookeeper>
      connection zookeeper.example.com:2181
      path /databases/demo
   </zookeeper>

   <filestorage>
      path demo.fs
   </filestorage>

.. -> server_conf

The ZEO configuration file has the same options as usual, plus a
``zookeeper`` section with two options:

``connection``
   A ZooKeeper connection string.  This is typically a list of
   *HOST:PORT* pairs separated by commas.

``path``
   The path at which to register the server.  The path must already
   exist.  When the server starts, it will register itself by creating
   a subnode of the path with a name consisting of it's address.

(You can also specify a ZooKeeper session timeout, in milliseconds,
with a ``session-timeout`` option.)

When specifying the ZEO address, you can leave off the port and the
operating system will assign it for you.

To start the server, use the ``zkrunzeo`` script::

  $ bin/zkrunzeo -C FILENAME

.. test

    >>> import zc.zkzeo.runzeo, zc.zk
    >>> stop = zc.zkzeo.runzeo.test(
    ...     server_conf)
    >>> zk = zc.zk.ZooKeeper('zookeeper.example.com:2181')
    >>> zk.print_tree('/databases/demo')
    /demo
      /127.0.0.1:56824
        pid = 88841

    >>> _ = stop()
    >>> zk.print_tree('/databases/demo')
    /demo

    >>> zk.close()

where ``FILENAME`` is the name of the configuration file you created.

Including a ``zc.monitor`` monitoring server
--------------------------------------------

The `zc.monitor <http://pypi.python.org/pypi/zc.monitor>`_ package
provides a simple extensible command server for gathering monitoring
data or providing run-time control of servers.  If ``zc.monitor`` is
in the Python path, ``zc.zkzeo`` can start a monitor server and make it's
address available as the ``monitor`` property of of a server's
ephemeral port.  To request this, we use a ``monitor-server`` option in
the ``zookeeper`` section::

   <zeo>
      address 127.0.0.1
   </zeo>

   <zookeeper>
      connection zookeeper.example.com:2181
      path /databases/demo
      monitor-server 127.0.0.1
   </zookeeper>

   <filestorage>
      path demo.fs
   </filestorage>

.. -> server_conf

    >>> stop = zc.zkzeo.runzeo.test(
    ...     server_conf)

The value is the address to listen on.

With the configuration above, if we started the server and looked at
the ZooKeeper tree for '/databases/demo' using the ``zc.zk`` package, we'd
see something like the following::

    >>> import zc.zk
    >>> zk = zc.zk.ZooKeeper('zookeeper.example.com:2181')
    >>> zk.print_tree('/databases/demo')
    /demo
      /127.0.0.1:64211
        monitor = u'127.0.0.1:11976'
        pid = 5082

Some notes on the monitor server:

- A monitor server won't be useful unless you've registered some
  command plugins.

- ``zc.monitor`` isn't a dependency of ``zc.zkzeoc`` and won't
  be in the Python path unless you install it.

Defining ZEO clients
====================

You can define a client in two ways, from Python and using a
configuration file.

Defining ZEO clients with Python
--------------------------------

From Python, use ``zc.zkzeo.client``::

    >>> import zc.zkzeo
    >>> client = zc.zkzeo.client(
    ...     'zookeeper.example.com:2181', '/databases/demo',
    ...     max_disconnect_poll=1)

You pass a ZooKeeper connection string and a path.  The ``Client``
constructor will create a client storage with addresses found as
sub-nodes of the given path and it will adjust the client-storage
addresses as nodes are added and removed as children of the path.

You can pass all other ``ZEO.ClientStorage.ClientStorage`` arguments,
except the address, as additional positional and keyword arguments.

Database and connection convenience functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You're usually not really interested in getting a storage object.
What you really want is a database object::

    >>> db = zc.zkzeo.DB(
    ...     'zookeeper.example.com:2181', '/databases/demo',
    ...     max_disconnect_poll=1)

or often, just a database connection::

    >>> conn = zc.zkzeo.connection(
    ...     'zookeeper.example.com:2181', '/databases/demo',
    ...     max_disconnect_poll=1)

.. test

   >>> exconn = conn

Defining ZEO clients in configuration files
-------------------------------------------

In configuration files, use a ``zkzeoclient`` storage
section::

    %import zc.zkzeo

    <zodb>
       <zkzeoclient>
          zookeeper zookeeper.example.com:2181
          server /databases/demo
          max-disconnect-poll 1
       </zkzeoclient>
    </zodb>

.. -> conf

The options for ``zkzeoclient`` are the same as for the standard ZODB
``zeoclient`` section, except:

- There's an extra required ``zookeeper`` option used to provide a
  ZooKeeper connection string.

- There can be only one ``server`` option and it is used to supply the
  path in ZooKeeper where addresses may be found.

.. test

  Double check the clients are working by opening a
  connection and making sure we see changes:

    >>> import ZODB.config
    >>> db_from_config = ZODB.config.databaseFromString(conf)
    >>> with db_from_config.transaction() as conn:
    ...     conn.root.x = 1

    >>> import ZODB
    >>> db_from_py = ZODB.DB(client)
    >>> with db_from_py.transaction() as conn:
    ...     print conn.root()
    {'x': 1}

    >>> with db.transaction() as conn:
    ...     print conn.root()
    {'x': 1}

    >>> import transaction
    >>> with transaction.manager:
    ...     print exconn.root()
    {'x': 1}

  When we stop the storage server, we'll get warnings from zc.zkzeo, the
  clients will disconnect and will have no addresses:

    >>> import zope.testing.loggingsupport
    >>> handler = zope.testing.loggingsupport.Handler('zc.zkzeo')
    >>> handler.install()

    >>> [old_addr] = zk.get_children('/databases/demo')

    >>> stop().exception

    >>> wait_until(lambda : not client.is_connected())
    >>> wait_until(lambda : not db_from_config.storage.is_connected())
    >>> wait_until(lambda : not db.storage.is_connected())
    >>> wait_until(lambda : not exconn.db().storage.is_connected())

    >>> print handler
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo WARNING
      No addresses from <zookeeper.example.com:2181/databases/demo>

    >>> handler.clear()

  Looking at the client manager, we see that the address list is now empty:

    >>> client._rpc_mgr
    <ConnectionManager for []>

  Let's sleep for a while to make sure we can wake up.  Of course, we
  won't sleep *that* long, it's a test.

    >>> import time
    >>> time.sleep(9)

  Now, we'll restart the server and clients will reconnect

    >>> stop = zc.zkzeo.runzeo.test(server_conf)

    >>> [addr] = zk.get_children('/databases/demo')
    >>> addr != old_addr
    True
    >>> print zk.export_tree('/databases/demo', ephemeral=True),
    /demo
      /127.0.0.1:56837
        monitor = u'127.0.0.1:23265'
        pid = 88841

    >>> wait_until(db_from_config.storage.is_connected)
    >>> with db_from_config.transaction() as conn:
    ...     conn.root.x = 2
    >>> wait_until(client.is_connected)
    >>> with db_from_py.transaction() as conn:
    ...     print conn.root()
    {'x': 2}

    >>> wait_until(db.storage.is_connected)
    >>> with db.transaction() as conn:
    ...     print conn.root()
    {'x': 2}

    >>> wait_until(exconn.db().storage.is_connected)
    >>> with transaction.manager:
    ...     print exconn.root()
    {'x': 2}

    >>> print handler # doctest: +NORMALIZE_WHITESPACE
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52649']
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52649']
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52649']
    zc.zkzeo WARNING
      OK: Addresses from <zookeeper.example.com:2181/databases/demo>
    zc.zkzeo INFO
      Addresses from <zookeeper.example.com:2181/databases/demo>:
      ['127.0.0.1:52649']

    >>> zk.close()
    >>> handler.uninstall()
    >>> db_from_py.close()
    >>> db_from_config.close()
    >>> db.close()
    >>> exconn.close()
    >>> stop().exception

Change History
==============

0.3.0 (2012-02-07)
------------------

- Added a static extra to force a dependency on
  ``zc-zookeeper-static``.

- In test mode, use a shorter asyncore loop timeout to make the server
  shut down faster.

- Fixed: zc.zkzeo depended on ``zc.zk [static]``, which forced
  installation of ``zc-zookeeper-static``, which should be optional.

- Fixed: tests didn't pass with a recent change in handling of
  registration with empty host names in ``zc.zk``.

- Fixed: Packaging: distribute can't install distributions with
  symlinks, so stopped using symlinks in distribution.

0.2.1 (2011-12-14)
------------------

- Fixed bug: The ``path`` key on the ``zookeeper``
  server-configuration section was required, and shouldn't have been.

0.2.0 (2011-12-13)
------------------

- Register the host name from the ZEO address setting with ZooKeeper.
  (This is often an empty string, which ``zc.zk`` turns into the
  fully-quelified domain name.)

- Fixed bug in handling the monitor-server. The actuall address
  setting was ignored.

0.1.1 (2011-12-12)
------------------

- Fixed a packaging bug.

0.1.0 (2011-12-11)
------------------

Initial release.
