"""Bluetooth Low Energy Python interface."""

import binascii
import io
import logging
import os
import queue
import subprocess

from functools import partial

from .btle import BTLEException, AssignedNumbers

SEC_LEVEL_LOW = "low"
SEC_LEVEL_MEDIUM = "medium"
SEC_LEVEL_HIGH = "high"


class Service:
    def __init__(self, protocol, uuidVal, hndStart, hndEnd):
        self.protocol = protocol
        self.uuidVal = uuidVal
        self.uuid = UUID(uuidVal)
        self.hndStart = hndStart
        self.hndEnd = hndEnd
        self.characteristics = None

    def getCharacteristics(self, forUUID=None, chars_cb=None):
        def set_chars(srv, forUUID, result=None):
            logging.debug('getCharacteristics cb: result %s' % result)
            assert isinstance(result, dict)

            srv.characteristics = result
            cb_result = result
            if forUUID is not None:
                u = UUID(forUUID)
                cb_result = [ch for ch in srv.characteristics if ch.uuid == u]
                logging.debug('forUUID=%s, result now is %s' % (forUUID, cb_result))

            return cb_result

        cb = CallbackChain(set_chars, forUUID)
        cb.concatenate(chars_cb)

        if not self.characteristics:  # Unset, or empty
            self.protocol.getCharacteristics(self.hndStart, self.hndEnd, cb)
        else:
            final_cb = CallbackChain(chars_cb, result=self.characteristics)
            self.protocol.enqueue_cb(final_cb)

    def __str__(self):
        return "Service <uuid=%s hadleStart=%s handleEnd=%s>" % (self.uuid,
                                                                 self.hndStart,
                                                                 self.hndEnd)


# KA: touched, unstable
class Characteristic(object):
    def __init__(self, protocol, uuidVal, handle, properties, valHandle):
        self.protocol = protocol
        self.uuidVal = uuidVal
        self.uuid = UUID(uuidVal)
        self.handle = handle
        self.properties = properties
        self.valHandle = valHandle

    def read(self):
        def cb(response_):
            logging.debug("Characteristic.read CB: whole resp %s" % response_)
            logging.debug("Characteristic.read CB: interesting %s" % response_['d'][0])
        self.protocol.send("rd %X" % self.handle, type_='rd', cb=cb)

    def write(self, val, withResponse=False):
        self.protocol.writeCharacteristic(self.valHandle, val, withResponse)

    # TODO: descriptors

    def __str__(self):
        return "Characteristic <%s>" % self.uuid


class Descriptor:
    def __init__(self, uuidVal, handle):
        self.uuidVal = uuidVal
        self.uuid = UUID(uuidVal)
        self.handle = handle

    def __str__(self):
        return "Descriptor <%s>" % self.uuid


class BLEHelperProcess(object):

    """BluePy Helper is a line based daemon which connects to a device.

    BluePy Helper uses Bluez to access a remote BLE device and interacts with
    it using a line oriented human readable text interface.

    An instance per device is required.

    This class interacts with the helper process.
    """
    __path = None
    stdin = stdout = stderr = subprocess.PIPE
    exitcode = None

    def __init__(self, path, stdin=None, stdout=None, stderr=None,
                 nonblocking=False):
        self.started = False
        self.__path = path
        if stdin is not None:
            self.stdin = stdin

        if stdout is not None:
            self.stdout = stdout

        if stderr is not None:
            self.stderr = stderr

    def start(self, restart=False):
        if self.started:
            if restart:
                logging.debug('restart=True: restaring helper')
                self.stop()
            else:
                return

        self.process = subprocess.Popen([self.__path],
                                        stdin=self.stdin,
                                        stdout=self.stdout,
                                        stderr=self.stderr,
                                        universal_newlines=True)

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
        return self._exitcode is None


class Transport(object):
    def __init__(self, process=None):
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
        return stdin.write(data + '\n')

    def readline(self, l=None, file_=None):
        assert isinstance(file_, (io.TextIOBase, type(None)))

        if self.process.is_alive():
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper exited")

        stdout = self.process.stdout if file_ is None else file_

        data = stdout.readline()
        logging.debug('readline: %s' % data)
        return data

    def connect(self, addr):
        assert len(addr.split(":")) != 6, "expected MAC, got %s" % addr

        self.deviceAddr = addr
        self.write("conn %s" % addr)

    def check_connect_response(self):
        line = self.readline()
        r = self.parse_line(line)
        return 'conn' in r

    def disconnect(self):
        if self.process is None:
            return
        self.write("disc")


class Protocol(object):
    def __init__(self, device_address):
        self.device_address = device_address
        self.services = {}  # Indexed by UUID
        self.discoveredAllServices = False

    def setUp(self, transport):
        assert isinstance(transport, Transport)

        self.transport = transport

    def line_received(self, line):
        """Method called when transport receives a line for this protocol"""
        parsed = self.parse_line(line)

        if 'rsp' not in parsed:
            logging.debug('receive_line: "rsp" response type not found: %s', parsed)
            return

        logging.debug('receive_line: response: %s', parsed)
        response_type = parsed['rsp'][0]
        self.trigger_callbacks_for_response_type(response_type, parsed)

    def trigger_callbacks_for_response_type(self, type_, response):
        q = self.get_callbacks_queue_for_type(type_)

        def queued_callback_generator(q):
            try:
                cb = q.get_nowait()
                yield CallbackChain(cb, response_=response)
            except queue.Empty:
                return

        for cb in queued_callback_generator(q):
            logging.debug('calling cb %s', cb)
            cb()

    @staticmethod
    def parse_line(line):
        resp = {}

        line, comment = line.strip().split('#', 1)
        resp['comment'] = comment

        if len(line) == 0:
            return resp

        for item in line.split(' '):
            # the assumption is that if there is a non-empty line, there are
            # also tag/text_val values in it
            tag, text_val = item.split('=')
            if not text_val:
                val = None
            elif text_val[0] == "$" or text_val[0] == "'":
                # Both symbols and strings as Python strings
                val = text_val[1:]
            elif text_val[0] == "h":
                # base 16 string to integer
                val = int(text_val[1:], base=16)
            elif text_val[0] == 'b':
                # string represantion of hex data to binary (bytes)
                val = binascii.a2b_hex(text_val[1:])
            else:
                raise BTLEException(BTLEException.INTERNAL_ERROR,
                                    "Cannot understand response value %s" %
                                    repr(text_val))
            if tag not in resp:
                resp[tag] = [val]
            else:
                resp[tag].append(val)
        # format is:
        # 'comment' present if comment found.
        # 'rsp' present if a response found.
        logging.debug('parse_line: resp %s', resp)
        return resp

    def wait_for_reponse_type(self, type_, cb, *args, **kw):
        """Wait to be called back when a selected response arrives"""
        if 'response_' in kw:
            raise RuntimeError('response_ kw arg passed as arg to cb %s' % cb)

        callback_chain = CallbackChain(cb, *args, **kw)
        self._append_response_queue_for_type(type_, callback_chain)

    def _call_cb_async(cb, *args, **kw):
        cb(*args, **kw)

    def get_callbacks_queue_for_type(self, type_):
        return self.__awaiting_responses[type_]

    def _append_response_queue_for_type(self, type_, partial_cb):
        q = self.__awaiting_responses.get(type_, None)
        if q is None:
            q = queue.Queue()
        q.put(partial_cb)

    def send(self, cmd, type_, cb, *args, **kw):
        self.wait_for_reponse_type(type_, cb, *args, **kw)
        self.transport.writeline(cmd)

    def status(self):
        def cb(response_):
            print('CB RESPONSE IS %s' % response_)
            assert response_['rsp'] == 'svcs'

        self.wait_for_reponse_type('stat', cb)
        self.send('stat')

    def discoverServices(self, disc_cb, *disc_args, **disc_kw):
        def cb(proto, response):
            assert response['rsp'] == 'svcs'
            assert isinstance(proto, Protocol), 'Protocol passed in cb'
            starts = response['hstart']
            ends = response['hend']
            uuids = response['uuid']
            nSvcs = len(uuids)
            assert len(starts) == nSvcs and len(ends) == nSvcs
            proto.services = {}
            for i in range(nSvcs):
                proto.services[UUID(uuids[i])] = Service(proto, uuids[i],
                                                         starts[i], ends[i])
            self.discoveredAllServices = True
            # TODO KA worth to trigger an action/callback
            logging.debug('discoveredAllServices: %s' % self.services)
            disc_cb(result=self.services.values(), *disc_args, **disc_kw)

        self.wait_for_reponse_type('svcs', cb, self)
        self.send('svcs')

    def getServices(self, srvs_cb, *srvs_args, **srvs_kw):
        if not self.discoveredAllServices:
            self.discoverServices(srvs_cb, *srvs_args, **srvs_kw)
        return srvs_cb(result=self.services.values(), *srvs_args, **srvs_kw)

    def getServiceByUUID(self, uuidVal, srvs_cb, *srvs_args, **srvs_kw):
        uuid = UUID(uuidVal)
        if uuid in self.services:
            return self.services[uuid]
        self._writeCmd("svcs %s\n" % uuid)
        rsp = self._getResp('find')
        svc = Service(self, uuid, rsp['hstart'][0], rsp['hend'][0])
        self.services[uuid] = svc
        return svc

    def _getIncludedServices(self, startHnd=1, endHnd=0xFFFF):
        # TODO: No working example of this yet
        self._writeCmd("incl %X %X\n" % (startHnd, endHnd))
        return self._getResp('find')

    def getCharacteristics(self, startHnd=1, endHnd=0xFFFF, uuid=None,
                           chars_cb=None, *chars_args, **chars_kw):
        assert chars_cb is not None, "getCharacteristics exists"
        cmd = 'char %X %X' % (startHnd, endHnd)
        if uuid:
            cmd += ' %s' % UUID(uuid)

        def cb(response_):
            logging.debug("getCharacteristics: cb resp=%s" % response_)
            nChars = len(response_['hnd'])
            ret = [Characteristic(self,
                                  response_['uuid'][i],
                                  response_['hnd'][i],
                                  response_['props'][i],
                                  response_['vhnd'][i])
                   for i in range(nChars)]
            logging.debug("getCharacteristics return %s" % ret)
            logging.debug("calling char cb")
            chars_cb(result=ret, *chars_args, **chars_kw)

        self.send(cmd, type_='find', cb=cb)

    def getDescriptors(self, startHnd=1, endHnd=0xFFFF,
                       desc_cb=None, *desc_args, **desc_kw):
        def cb(response_):
            nDesc = len(response_['hnd'])
            ret = [Descriptor(self, response_['uuid'][i], response_['hnd'][i])
                   for i in range(nDesc)]
            logging.debug("getDescriptors result %s" % ret)
            logging.debug("calling desc cb")
            desc_cb(result=ret, *desc_args, **desc_kw)

        self.send("desc %X %X\n" % (startHnd, endHnd), type_='desc', cb=cb)

#    def _readCharacteristicByUUID(self, uuid, startHnd, endHnd):
#        # Not used at present
#        self._writeCmd("rdu %s %X %X\n" % (UUID(uuid), startHnd, endHnd))
#        return self._getResp('rd')

    def writeCharacteristic(self, handle, val, withResponse=False,
                            write_cb=None, *write_args, **write_kw):
        def cb(response_):
            logging.debug("writeCharacteristic resp %s" % response_)
            write_cb(result=response_['wr'], *write_args, **write_kw)

        cmd = "wrr" if withResponse else "wr"
        self.send("%s %X %s\n" % (cmd, handle, binascii.b2a_hex(val)),
                  type='wr', cb=cb)
        return self._getResp('wr')

#    def setSecurityLevel(self, level):
#        self._writeCmd("secu %s\n" % level)
#        return self._getResp('stat')

#    def setMTU(self, mtu):
#        self._writeCmd("mtu %x\n" % mtu)
#        return self._getResp('stat')
