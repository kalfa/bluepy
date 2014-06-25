"""Bluetooth Low Energy Python interface."""

import binascii
import collections
import logging
import queue

from .common import BTLEException
from .utils import UUID
from .callbacks import CallbackChain
from .transport import Transport

SEC_LEVEL_LOW = "low"
SEC_LEVEL_MEDIUM = "medium"
SEC_LEVEL_HIGH = "high"


# class Service:
#    def __init__(self, protocol, uuidVal, hndStart, hndEnd):
#        self.protocol = protocol
#        self.uuidVal = uuidVal
#        self.uuid = UUID(uuidVal)
#        self.hndStart = hndStart
#        self.hndEnd = hndEnd
#        self.characteristics = None
#
#    def getCharacteristics(self, forUUID=None, chars_cb=None):
#        def set_chars(srv, forUUID, result_):
#            logging.debug('getCharacteristics cb: result %s' % result_)
#            assert isinstance(result_, dict)
#
#            srv.characteristics = result_
#            cb_result = result_
#            if forUUID is not None:
#                u = UUID(forUUID)
#                cb_result = [ch for ch in srv.characteristics if ch.uuid == u]
#                logging.debug('forUUID=%s, result now is %s' % (forUUID, cb_result))
#
#            return cb_result
#
#        if not self.characteristics:  # Unset, or empty
#            cb = CallbackChain(set_chars, forUUID=forUUID)
#            cb.put(chars_cb)
#            self.protocol.getCharacteristics(self.hndStart, self.hndEnd, cb)
#        else:
#            final_cb = CallbackChain(chars_cb)
#            final_cb.set_result(self.characteristics)
#            self.protocol._call_cb_async(final_cb)
#
#    def __str__(self):
#        return "Service <uuid=%s hadleStart=%s handleEnd=%s>" % (self.uuid,
#                                                                 self.hndStart,
#                                                                 self.hndEnd)


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

        self.__default_cb = {}
        self.add_default_callback('stat', self.__on_stat)

    def init(self, transport):
        assert isinstance(transport, Transport)

        self.transport = transport

    def __on_stat(self, result_):
        logging.debug('default stat CB: %s' % result_)
        if 'conn' in result_['state']:
            logging.debug('setting connection state for transport')
            self.transport._setconnectedstate(dst=result_['dst'],
                                              mtu=result_['mtu'],
                                              sec=result_['sec'])
        elif 'disc' in result_['state']:
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

    def trigger_callbacks_for_response_type(self, type_, response):
        q = self.get_callbacks_queue_for_type(type_)
        default_q = self.__default_cb.get(type_, None)
        default_at_start = True
        if default_q is not None:
            if type_ == 'conn' and 'disc' in response['mode']:
                # call the 'disconnect' callback as last
                default_at_start = False
                # at disconnect time first registered cb should be the last to
                # be called, last one first.
                default_q = default_q[:]
                default_q.reverse()

        def queued_callback_generator(q, default_q, default_at_start):
            """Return a generator yielding CallbackChain instances"""
            try:
                if default_at_start and isinstance(default_q,
                                                   collections.Iterable):
                    for cb in default_q:
                        # it's a reusable cb, set_result will raise on a second
                        # call
                        cb.result = response
                        yield cb
                while True:
                    cb = q.get_nowait()
                    cb.set_result(response)
                    yield cb
            except queue.Empty:
                if not default_at_start and isinstance(default_q,
                                                       collections.Iterable):
                    for cb in default_q:
                        # it's a reusable cb, set_result will raise on a second
                        # call
                        cb.result = response
                        yield cb

                    raise StopIteration()

        return queued_callback_generator(q, default_q, default_at_start)

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

    def add_default_callback(self, type_, cb, *args, **kw):
        """Add a cb as default handler for type_

        callback needs to return None
        """
        assert callable(cb), 'default cb for %s is callable' % type_


        if isinstance(cb, CallbackChain):
            cb.append_partial_params(*args, **kw)
        else:
            cb = CallbackChain(cb, *args, **kw)

        if self.__default_cb.get(type_, None) is None:
            self.__default_cb[type_] = []

        self.__default_cb[type_].append(cb)

    def wait_for_response_type(self, type_, cb, *args, **kw):
        """Wait to be called back when a selected response arrives

        @param type_: string representing the value of rsp field in the result
        @param cb: a callable, e.g. a CallbackChain
        @param args: positional args to be passed to cb. If cb is a
          CallbackChain, they will be appended as partial args
        @param kw: keyword args to be passed to cb. If cb is a CallbackChain,
          they will be appended as partial args.
        """
        assert callable(cb), "callback is a callable"
        if 'result_' in kw:
            raise RuntimeError('result_ kw arg passed as arg to cb %s' % cb)

        if isinstance(cb, CallbackChain):
            cb.append_partial_params(*args, **kw)
            callback_chain = cb
        else:
            callback_chain = CallbackChain(cb, *args, **kw)
        self._append_response_queue_for_type(type_, callback_chain)

    def _call_cb_async(cb, *args, **kw):
        raise NotImplemented()

    def get_callbacks_queue_for_type(self, type_):
        return self.__awaiting_responses.get(type_, queue.Queue())

    def _append_response_queue_for_type(self, type_, partial_cb):
        q = self.__awaiting_responses.get(type_, None)
        if q is None:
            q = queue.Queue()
            self.__awaiting_responses[type_] = q
        q.put(partial_cb)

    def send(self, cmd, type_, cb, *args, **kw):
        self.wait_for_response_type(type_, cb, *args, **kw)
        self.transport.writeline(cmd)

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
#    def getServiceByUUID(self, uuidVal, srvs_cb, *srvs_args, **srvs_kw):
#        uuid = UUID(uuidVal)
#        if uuid in self.services:
#            return self.services[uuid]
#
#        self.writeline("svcs %s" % uuid)
#
#
#
#        rsp = self._getResp('find')
#        svc = Service(self, uuid, rsp['hstart'][0], rsp['hend'][0])
#        self.services[uuid] = svc
#        return svc
#
#    def _getIncludedServices(self, startHnd=1, endHnd=0xFFFF):
#        # TODO: No working example of this yet
#        self._writeCmd("incl %X %X\n" % (startHnd, endHnd))
#        return self._getResp('find')

    def getCharacteristics(self, startHnd=1, endHnd=0xFFFF, uuid=None,
                           chars_cb=None, *chars_args, **chars_kw):
        cmd = 'char %X %X' % (startHnd, endHnd)
        if uuid:
            cmd += ' %s' % UUID(uuid)

        def get_chars(result_):
            logging.debug("getCharacteristics: cb resp=%s" % result_)
            nChars = len(result_['hnd'])
            ret = [Characteristic(self,
                                  result_['uuid'][i],
                                  result_['hnd'][i],
                                  result_['props'][i],
                                  result_['vhnd'][i])
                   for i in range(nChars)]
            logging.debug("getCharacteristics return %s" % ret)
            return ret

        cb = CallbackChain(get_chars)
        if callable(chars_cb):
            if isinstance(chars_cb, CallbackChain):
                chars_cb.append_partial_params(*chars_cb, **chars_kw)
                chars = chars_cb
            else:
                chars = CallbackChain(chars_cb, *chars_args, **chars_kw)
            cb.put(chars)
        self.send(cmd, type_='find', cb=cb)

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

    def writeCharacteristic(self, handle, val, withResponse=False,
                            write_cb=None, *write_args, **write_kw):
        def logger(response_):
            logging.debug("writeCharacteristic resp %s" % response_)
            return response_

        cb = CallbackChain(logger)
        if callable(write_cb):
            if isinstance(write_cb, CallbackChain):
                write_cb.append_partial_params(*write_args, **write_kw)
                writer = write_cb
            else:
                writer = CallbackChain(write_cb, *write_args, **write_kw)
            cb.put(writer)

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
