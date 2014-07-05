import logging
import io
import os
import subprocess

from .common import BTLEException


class BLEHelperProcess(object):

    """BluePy Helper is a line based daemon which connects to a device.

    BluePy Helper uses Bluez to access a remote BLE device and interacts with
    it using a line oriented human readable text interface.

    An instance per device is required.

    This class interacts with the helper process.
    """
    __path = None
    _stdin = _stdout = _stderr = subprocess.PIPE
    exitcode = None

    def __init__(self, path, stdin=None, stdout=None, stderr=None,
                 nonblocking=False):
        self.started = False
        self.__path = path
        if stdin is not None:
            self._stdin = stdin

        if stdout is not None:
            self._stdout = stdout

        if stderr is not None:
            self._stderr = stderr

    def start(self, restart=False):
        if self.started:
            if restart:
                logging.debug('restart=True: restaring helper')
                self.stop()
            else:
                return

        self.process = subprocess.Popen([self.__path],
                                        stdin=self._stdin,
                                        stdout=self._stdout,
                                        stderr=self._stderr,
                                        universal_newlines=True)
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.stderr = self.process.stderr

    def stop(self):
        if not self.started:
            return

        logging.debug("Stopping ", self.__path)
        self.process.stdin.write("quit\n")
        stdout, stderr = self.process.communicate()
        self.process = None
        logging.debug("process terminated. Output on exit: %s" % stdout)
        if stderr:
            logging.debug("Stderr on exit: %s" % stdout)

    def is_alive(self):
        self.exitcode = self.process.poll()
        return self.exitcode is None


class Transport(object):
    connected = False

    def __init__(self, process=None):
        assert isinstance(process, (type(None), BLEHelperProcess)), process

        if process is not None:
            self.process = process
        else:
            helper_path = os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                "bluepy-helper")
            self.process = BLEHelperProcess(helper_path)

    def writeline(self, data, file_=None):
        assert isinstance(file_, (io.TextIOBase, type(None))), \
            'file is None or a file object instance'
        assert data[-1] != '\n', 'newline character not present'

        if self.process is None:
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper not started")

        stdin = self.process.stdin if file_ is None else file_

        logging.debug('writeline: sent %s' % data)
        return stdin.write('%s\n' % data)

    def readline(self, file_=None):
        assert isinstance(file_, (io.TextIOBase, type(None)))

        if not self.process:
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper not started")
        if not self.process.is_alive():
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper exited")

        stdout = self.process.stdout if file_ is None else file_

        data = stdout.readline()
        logging.debug('readline: %s' % data)
        return data

    def _setconnectedstate(self, dst, mtu, sec):
        self._dst = dst
        self._mtu = mtu
        self._sec = sec

    def connect(self, addr):
        assert len(addr.split(":")) == 6, "expected MAC, got %s" % addr

        if self.connected:
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper already connected to %s" % addr)

        self.writeline("conn %s" % addr)

    def disconnect(self):
        if self.process is None:
            return
        self.writeline("disc")
