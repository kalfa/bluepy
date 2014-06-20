"""Bluetooth Low Energy Python interface."""

import sys
import os
import time
import subprocess
import binascii


SEC_LEVEL_LOW = "low"
SEC_LEVEL_MEDIUM = "medium"
SEC_LEVEL_HIGH = "high"


def DBG(*args):
    if Debugging:
        msg = " ".join([str(a) for a in args])
        print(msg)


class BTLEException(Exception):

    """BTLE Exception."""

    DISCONNECTED = 1
    COMM_ERROR = 2
    INTERNAL_ERROR = 3

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return '%d: %s' % (self.errmap[self.code], self.message)


class UUID:
    def __init__(self, val):
        '''We accept: 32-digit hex strings, with and without '-' characters,
           4 to 8 digit hex strings, and integers'''
        if isinstance(val, int):
            if (val < 0) or (val > 0xFFFFFFFF):
                raise ValueError(
                    "Short form UUIDs must be in range 0..0xFFFFFFFF")
            val = "%04X" % val
        elif isinstance(val, self.__class__):
            val = str(val)
        else:
            val = str(val)  # Do our best

        val = val.replace("-", "")
        if len(val) <= 8:  # Short form
            val = ("0" * (8 - len(val))) + val + "00001000800000805F9B34FB"

        self.binVal = binascii.a2b_hex(val)
        if len(self.binVal) != 16:
            raise ValueError(
                "UUID must be 16 bytes, got '%s' (len=%d)" % (val,
                                                              len(self.binVal)))

    def __str__(self):
        s = binascii.b2a_hex(self.binVal).decode('utf-8')
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:32]])

    def __eq__(self, other):
        return self.binVal == UUID(other).binVal

    def __cmp__(self, other):
        return cmp(self.binVal, UUID(other).binVal)

    def __hash__(self):
        return hash(self.binVal)

    def friendlyName(self):
        #TODO
        return str(self)

class Service:
    def __init__(self, *args):
        (self.peripheral, uuidVal, self.hndStart, self.hndEnd) = args
        self.uuid = UUID(uuidVal)
        self.chars = None

    def getCharacteristics(self, forUUID=None):
        if not self.chars: # Unset, or empty
            self.chars = self.peripheral.getCharacteristics(self.hndStart, self.hndEnd)
        if forUUID is not None:
            u = UUID(forUUID)
            return [ch for ch in self.chars if ch.uuid==u]
        return self.chars

    def __str__(self):
        return "Service <uuid=%s hadleStart=%s handleEnd=%s>" % (self.uuid,
                                                                 self.hndStart,
                                                                 self.hndEnd)
# KA: touch, unstable
class Characteristic(BasePeripheral):
    def __init__(self, uuidVal, handle, properties, valHandle):
        self.uuidVal = uuidVal
        self.handle = handle
        self.properties = properties
        self.valHandle = valHandle
        self.uuid = UUID(uuidVal)

    def read(self):
        self._writeCmd("rd %X\n" % self.handle)
        resp = self._getResp('rd')
        return resp['d'][0]



    def write(self, val, withResponse=False):
        self.peripheral.writeCharacteristic(self.valHandle, val, withResponse)

    # TODO: descriptors

    def __str__(self):
        return "Characteristic <%s>" % self.uuid

class Descriptor:
    def __init__(self, *args):
        (self.peripheral, uuidVal, self.handle) = args
        self.uuid = UUID(uuidVal)

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

    def __init__(self, path, stdin=None, stdout=None, stderr=None, nonblocking=False):
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

        DBG("Stopping ", helperExe)
        self.process.stdin.write("quit\n")
        stdout, stderr = self.process.communicate()
        self.process = None
        DBG("process terminated. Output on exit: %s" % stdout)
        if stderr:
            DBG("Stderr on exit: %s" % stdout)

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

        DBG('writeline: sent %s' % data)
        return stdin.write(data + '\n')

    def readline(self, l=None, file_=None):
        assert isinstance(file_, (io.TextIOBase, type(None)))

        if self.process.is_alive():
            raise BTLEException(BTLEException.INTERNAL_ERROR,
                                "Helper exited")

        stdout = self.process.stdout if file_ is None else file_

        data = stdout.readline()
        DBG('readline: %s' % data)
        return data

    def connect(self, addr):
        assert len(addr.split(":")) != 6, "expected MAC, got %s", addr

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
    def __init__(self, deviceAddr=None):
        self.services = {} # Indexed by UUID
        self.discoveredAllServices = False

    def setUp(self, transport):
        assert isinstance(transport, Transport)

        self.transport = transport


    def receive_line(self, line):
        parsed = self.parse_line(line)

        if 'rsp' not in parsed:
            DBG('receive_line: "rsp" response type not found: %s', parsed)
            return

        response_type = parsed['rsp'][0]
        self.trigger_callbacks_for_response_type(response_type, parsed)

    def trigger_callbacks_for_response_type(self, type_, response):
        q = self.get_callbacks_queue_for_type(type_)
        def queued_callback_generator(q):
            try:
                cb = q.get_nowait()
                yield cb(response=response)
            except queue.Empty:
                return

        for cb in queued_callback_generator(q):
            DBG('calling cb %s', q)
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
            # also tag/tval values in it
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
                                    repr(tval))
            if tag not in resp:
                resp[tag] = [val]
            else:
                resp[tag].append(val)
        # format is:
        # 'comment' present if comment found.
        # 'rsp' present if a response found.
        DBG('parse_line: resp %s', resp)
        return resp

    def wait_for_reponse_type(self, type_, cb, *args, **kw):
        cb = partial(cb, *args, **kw)
        self._append_response_queue_for_type(type_, partial_cb)

    def get_callbacks_queue_for_type(self, type_):
        return self.__awaiting_responses[type_]

    def _append_response_queue_for_type(self, type_, partial_cb)
        q = self.__awaiting_responses.get(type_, None)
        if q is None:
            q = Queue()
        q.put(partial_cb)

    def send(self, cmd):
        self.wait_for_reponse_type
        self.transport.writeline(cmd)

    def status(self):
        def cb(response):
            print('CB RESPONSE IS %s' % response)
            assert response['rsp'] == 'svcs'

        self.wait_for_reponse_type('stat', cb)
        self.send('stat')


    def discoverServices(self):
        self.send('svcs')
        def cb(proto, response):
            assert response['rsp'] == 'svcs'
            assert isinstance(prooto, Protocol), 'Protocol passed in cb'
            starts = response['hstart']
            ends   = response['hend']
            uuids  = response['uuid']
            nSvcs = len(uuids)
            assert(len(starts) == nSvcs and len(ends) == nSvcs)
            proto.services = {}
            for i in range(nSvcs):
                proto.services[UUID(uuids[i])] = Service(proto, uuids[i], starts[i], ends[i])
            self.discoveredAllServices = True
            # TODO KA worth to trigger an action/callback
            return self.services  # TODO remove me, pointless KA
        self.wait_for_reponse_type('svcs', cb, self)

    def getServices(self):
        if not self.discoveredAllServices:
            self.discoverServices()
        # TODO KA find a way to callback
        return self.services.values()

    def getServiceByUUID(self, uuidVal):
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

    def getCharacteristics(self, startHnd=1, endHnd=0xFFFF, uuid=None):
        cmd = 'char %X %X' % (startHnd, endHnd)
        if uuid:
            cmd += ' %s' % UUID(uuid)
        self._writeCmd(cmd + "\n")
        rsp = self._getResp('find')
        nChars = len(rsp['hnd'])
        return [Characteristic(self, rsp['uuid'][i], rsp['hnd'][i],
                               rsp['props'][i], rsp['vhnd'][i])
                for i in range(nChars)]

    def getDescriptors(self, startHnd=1, endHnd=0xFFFF):
        self._writeCmd("desc %X %X\n" % (startHnd, endHnd) )
        resp = self._getResp('desc')
        nDesc = len(resp['hnd'])
        return [Descriptor(self, resp['uuid'][i], resp['hnd'][i]) for i in
                range(nDesc)]

    def _readCharacteristicByUUID(self, uuid, startHnd, endHnd):
        # Not used at present
        self._writeCmd("rdu %s %X %X\n" % (UUID(uuid), startHnd, endHnd))
        return self._getResp('rd')

    def writeCharacteristic(self, handle, val, withResponse=False):
        cmd = "wrr" if withResponse else "wr"
        self._writeCmd("%s %X %s\n" % (cmd, handle, binascii.b2a_hex(val)))
        return self._getResp('wr')

    def setSecurityLevel(self, level):
        self._writeCmd("secu %s\n" % level)
        return self._getResp('stat')

    def setMTU(self, mtu):
        self._writeCmd("mtu %x\n" % mtu)
        return self._getResp('stat')

    def __del__(self):
        self.disconnect()

class AssignedNumbers:
    # TODO: full list
    deviceName   = UUID("2A00")
    txPowerLevel = UUID("2A07")
    batteryLevel = UUID("2A19")
    modelNumberString = UUID("2A24")
    serialNumberString = UUID("2A25")
    firmwareRevisionString = UUID("2A26")
    hardwareRevisionString = UUID("2A27")
    softwareRevisionString = UUID("2A28")
    manufacturerNameString = UUID("2A29")

    nameMap = {
        deviceName : "Device Name",
        txPowerLevel : "Tx Power Level",
        batteryLevel : "Battery Level",
        modelNumberString : "Model Number String",
        serialNumberString : "Serial Number String",
        firmwareRevisionString : "Firmware Revision String",
        hardwareRevisionString : "Hardware Revision String",
        softwareRevisionString : "Software Revision String",
        manufacturerNameString : "Manufacturer Name String",
    }

    @staticmethod
    def getCommonName(uuid):
        assert isinstance(uuid, UUID), '%s not a UUID instance' % uuid
        return AssignedNumbers.nameMap.get(uuid, None)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("Usage:\n  %s <mac-address>" % sys.argv[0])

    Debugging = False
    helperExe = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             "bluepy-helper")
    if not os.path.isfile(helperExe):
        raise ImportError("Cannot find required executable '%s'" % helperExe)

    devaddr = sys.argv[1]
    print("Connecting to:", devaddr)
    conn = Peripheral(devaddr)
    try:
        for svc in conn.getServices():
            print(str(svc), ":")
            for ch in svc.getCharacteristics():
                print("    " + str(ch))
                chName = AssignedNumbers.getCommonName(ch.uuid)
                if chName is not None:
                    print("    ->", chName, repr(ch.read()))
    finally:
        if conn is not None:
            conn.disconnect()
