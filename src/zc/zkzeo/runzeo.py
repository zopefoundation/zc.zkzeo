import asyncore
import os
import select
import sys
import threading
import time
import zc.thread
import zc.zk
import ZEO.runzeo

class Options(ZEO.runzeo.ZEOOptions):

    __doc__ = ZEO.runzeo.__doc__ + """

    This command supports registering a server with ZooKeeper.
    """
    schemadir = os.path.dirname(__file__)

    def __init__(self):
        ZEO.runzeo.ZEOOptions.__init__(self)

        self.add('zkconnection', 'zookeeper.connection')
        self.add('zkpath', 'zookeeper.path')
        self.add('zookeeper_session_timeout', 'zookeeper.session_timeout')
        self.add('monitor_server', 'zookeeper.monitor_server')

class ZKServer(ZEO.runzeo.ZEOServer):

    __zk = __testing = __using_dynamic_port = None
    def create_server(self):
        ZEO.runzeo.ZEOServer.create_server(self)
        if self.__testing is not None:
            # Make the loop dies quickly when we close the storage
            # XXX should find a way to do this wo monkey patching. :/
            self.server.loop = (
                lambda : asyncore.loop(.1, map=self.server.socket_map))
        if not self.options.zkpath:
            return

        addr = (self.server.addr[0],
                self.server.dispatcher.socket.getsockname()[1])
        def register():

            props = {}
            if self.options.monitor_server:
                global zc
                import zc.monitor

                maddr = self.options.monitor_server.address
                if isinstance(maddr, tuple) and maddr[1] is None:
                    maddr = maddr[0], 0

                maddr = zc.monitor.start(maddr)
                if isinstance(maddr, tuple):
                    props['monitor'] = "%s:%s" % maddr

            self.__zk.register_server(self.options.zkpath, addr[:2], **props)
            if self.__testing is not None:
                self.__testing()

        if self.__using_dynamic_port:
            self.__zk = zc.zk.ZooKeeper(
                self.options.zkconnection,
                self.options.zookeeper_session_timeout,
                )
            register()
            return

        @zc.thread.Thread
        def zookeeper_registration_thread():
            self.__zk = zc.zk.ZooKeeper(
                self.options.zkconnection,
                self.options.zookeeper_session_timeout,
                wait = True,
                )
            register()

    def clear_socket(self):
        if self.__zk is not None:
            self.__zk.close()
        ZEO.runzeo.ZEOServer.clear_socket(self)

    def check_socket(self):
        if not self.options.address[1]:
            self.options.address = self.options.address[0], 0
            self.__using_dynamic_port = True
            return
        ZEO.runzeo.ZEOServer.check_socket(self)

    def setup_signals(self):
        if self.__testing is not None:
            return
        ZEO.runzeo.ZEOServer.setup_signals(self)

    def setup_default_logging(self):
        if self.__testing is not None:
            return
        ZEO.runzeo.ZEOServer.setup_default_logging(self)


def main(args=None, testing=None):
    if args is None:
        args = sys.argv[1:]
    options = Options()
    options.realize(args)
    s = ZKServer(options)
    s._ZKServer__testing = testing
    if testing is not None:
        return s
    s.main()

def test(config, storage=None, zookeeper=None, threaded=True):
    """Run a server in a thread, mainly for testing.
    """
    import tempfile

    if '\n' not in config:
        # It's just a path
        if storage is None:
            storage = '<mappingstorage>\n</mappingstorage>'
        elif storage.endswith('.fs'):
            storage = '<filestorage>\npath %s\n</filestorage>' % storage
        config = """
        <zeo>
          address 127.0.0.1
        </zeo>
        <zookeeper>
          connection %s
          path %s
        </zookeeper>
        %s
        """ % (zookeeper, config, storage)

    fd, confpath = tempfile.mkstemp()
    os.write(fd, config)
    os.close(fd)
    event = threading.Event()
    server = main(['-C', confpath], event.set)

    os.remove(confpath)

    run_zeo_server_for_testing = None

    def stop():
        server.server.close()
        assert not server.server.dispatcher._map, server.server.dispatcher._map

        if run_zeo_server_for_testing is not None:
            run_zeo_server_for_testing.join(11)
            assert not run_zeo_server_for_testing.is_alive()
            return run_zeo_server_for_testing

    if not threaded:
        try:
            return server.main()
        except:
            stop()
            raise

    @zc.thread.Thread
    def run_zeo_server_for_testing():
        import asyncore
        try:
            server.main()
        except select.error:
            pass
        except:
            import logging
            logging.getLogger(__name__+'.test').exception(
                'wtf %r', sys.exc_info()[1])

    stop.server = server # :)

    event.wait(1)
    return stop
