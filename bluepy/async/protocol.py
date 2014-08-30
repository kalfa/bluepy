"""Bluetooth Low Energy Python interface."""

import binascii
import logging

from functools import partial

from .common import BTLEException
from .utils import UUID
from .callbacks import MultiverseFuture
from .transport import Transport

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

    def getCharacteristics(self, forUUID=None):
        def set_chars(srv, forUUID, future):
            srv.characteristics = future.result()
            logging.debug('getCharacteristics cb: result %s' % srv.characteristics)

            if forUUID is None:
                return srv.characteristics

            u = UUID(forUUID)
            filtered_chars = [ch for ch in srv.characteristics if ch.uuid == u]
            logging.debug('forUUID=%s, result now is %s' % (forUUID, filtered_chars))
            return filtered_chars

        returned_future = MultiverseFuture()
        if not self.characteristics:
            f = self.protocol.getCharacteristics(self.hndStart, self.hndEnd)
            f.add_done_chained_callback(partial(set_chars, self, forUUID=forUUID))
            f.add_done_chained_future(returned_future)
        else:
            returned_future.set_result(self.characteristics)

        return returned_future

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
        # self.properties = properties
        self.valHandle = valHandle

    def read(self, cb, *args, **kw):
        self.protocol.send("rd %X" % self.handle, type_='rd', cb=None, *args, **kw)

    def write(self, val, withResponse=False, cb=None, *args, **kw):
        self.protocol.writeCharacteristic(self.valHandle, val, withResponse,
                                          cb, *args, **kw)

    # TODO: descriptors

    def __str__(self):
        return "Characteristic <%s>" % self.uuid


# class Descriptor:
#    def __init__(self, uuidVal, handle):
#        self.uuidVal = uuidVal
#        self.uuid = UUID(uuidVal)
#        self.handle = handle
#
#    def __str__(self):
#        return "Descriptor <%s>" % self.uuid


class Protocol(object):
    def __init__(self):
        self.services = {}  # Indexed by UUID
        self.discoveredAllServices = False
        self.__awaiting_responses = {}

        f = self.get_default_handler_for('stat')
        f.add_done_chained_callback(self.__on_stat)

    def init(self, transport):
        assert isinstance(transport, Transport)

        self.transport = transport

    def __on_stat(self, future):
        assert future.done(), 'future is not running or pending'
        result = future.result()
        logging.debug('default stat CB: %s' % result)
        if 'conn' in result['state']:
            logging.debug('setting connection state for transport')
            self.transport._setconnectedstate(dst=result['dst'],
                                              mtu=result['mtu'],
                                              sec=result['sec'])
        elif 'disc' in result['state']:
            logging.debug('disconnect transport')
            self.transport.disconnect()

    def line_received(self, line):
        """Method called when transport receives a line for this protocol"""
        parsed = self.parse_line(line)

        if 'rsp' not in parsed and 'comment' not in parsed:
            logging.debug('receive_line: "rsp" response type not found: %s',
                          parsed)
            raise BTLEException(BTLEException.COMM_ERROR,
                                'responose not recognized %s' % parsed)

        logging.debug('line_received: %s', parsed)
        if 'rsp' in parsed:
            response_type = parsed['rsp'][0]
        else:
            response_type = 'comment'
        return response_type, parsed

    @staticmethod
    def parse_line(line):
        resp = {}

        line = line.strip()

        if line.startswith('#'):
            resp['comment'] = line[1:]
            return resp

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
        return resp

    def send(self, cmd):
        return self.transport.writeline(cmd)

#    def status(self):
#        def cb(response_):
#            print('CB RESPONSE IS %s' % response_)
#            assert response_['rsp'] == 'svcs'
#
#        self.wait_for_response_type('stat', cb)
#        self.send('stat')

#    def discoverServices(self, disc_cb, *disc_args, **disc_kw):
#        def cb(proto, response):
#            assert response['rsp'] == 'svcs', 'expect rsp=svcs'
#            assert isinstance(proto, Protocol), 'Protocol is passed to cb'
#
#            starts = response['hstart']
#            ends = response['hend']
#            uuids = response['uuid']
#            nSvcs = len(uuids)
#            assert len(starts) == nSvcs and len(ends) == nSvcs
#
#            proto.services = {}
#            for i in range(nSvcs):
#                proto.services[UUID(uuids[i])] = Service(proto, uuids[i],
#                                                         starts[i], ends[i])
#            self.discoveredAllServices = True
#            # TODO KA worth to trigger an action/callback
#            logging.debug('discoveredAllServices: %s' % self.services)
#            disc_cb(result_=self.services.values(), *disc_args, **disc_kw)
#
#        self.wait_for_response_type('svcs', cb, self)
#        self.send('svcs')
#
#    def getServices(self, srvs_cb, *srvs_args, **srvs_kw):
#        if not self.discoveredAllServices:
#            self.discoverServices(srvs_cb, *srvs_args, **srvs_kw)
#        return srvs_cb(result_=self.services.values(), *srvs_args, **srvs_kw)
#
    def getServiceByUUID(self, uuidVal):
        """CB returns a Service instance"""
        uuid = UUID(uuidVal)

        def get_srvs(future):
            """CB for discovering UUID"""
            result = future.result()
            svc = Service(self, uuid, result['hstart'][0], result['hend'][0])
            self.services[uuid] = svc
            return svc

        if uuid in self.services:
            f = MultiverseFuture()
            f.set_result(self.services[uuid])
        else:
            f = self.send('svcs %s' % uuid)  # type=find
            f.add_done_chained_callback(get_srvs)

        return f

#    def _getIncludedServices(self, startHnd=1, endHnd=0xFFFF):
#        # TODO: No working example of this yet
#        self._writeCmd("incl %X %X\n" % (startHnd, endHnd))
#        return self._getResp('find')

    def getCharacteristics(self, startHnd=1, endHnd=0xFFFF, uuid=None):
        cmd = 'char %X %X' % (startHnd, endHnd)
        if uuid:
            cmd += ' %s' % UUID(uuid)

        def get_chars(future):
            """Transforms the read result in a list of Characteristic
            instances"""
            result = future.result()
            logging.debug("getCharacteristics: cb resp=%s" % result)
            nChars = len(result['hnd'])
            ret = [Characteristic(self,
                                  result['uuid'][i],
                                  result['hnd'][i],
                                  result['props'][i],
                                  result['vhnd'][i])
                   for i in range(nChars)]
            logging.debug("getCharacteristics return %s" % ret)
            return ret

        f = self.send(cmd)
        f.add_done_chained_callback(get_chars)
        return f

#    def getDescriptors(self, startHnd=1, endHnd=0xFFFF,
#                       desc_cb=None, *desc_args, **desc_kw):
#        def cb(response_):
#            nDesc = len(response_['hnd'])
#            ret = [Descriptor(self, response_['uuid'][i], response_['hnd'][i])
#                   for i in range(nDesc)]
#            logging.debug("getDescriptors result %s" % ret)
#            logging.debug("calling desc cb")
#            desc_cb(result=ret, *desc_args, **desc_kw)
#
#        self.send("desc %X %X\n" % (startHnd, endHnd), type_='desc', cb=cb)

#    def _readCharacteristicByUUID(self, uuid, startHnd, endHnd):
#        # Not used at present
#        self._writeCmd("rdu %s %X %X\n" % (UUID(uuid), startHnd, endHnd))
#        return self._getResp('rd')

    def writeCharacteristic(self, handle, val, withResponse=False):
        def logger(future):
            logging.debug("writeCharacteristic resp %s" % future.result())
            return future

        cmd = "wrr" if withResponse else "wr"
        f = self.send("%s %X %s\n" % (cmd, handle,
                                      binascii.b2a_hex(val)))  # type=wr
        f.add_done_chained_callback(logger)
        return f

#    def setSecurityLevel(self, level):
#        self._writeCmd("secu %s\n" % level)
#        return self._getResp('stat')

#    def setMTU(self, mtu):
#        self._writeCmd("mtu %x\n" % mtu)
#        return self._getResp('stat')
