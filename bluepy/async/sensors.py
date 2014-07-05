"""Sensirion SHTC1 BLE classes."""

import logging
import struct

from .utils import UUID
from .protocol import Protocol


def _TI_UUID(val):
    """Get TI UUID from short UUID."""
    return UUID("%08X-0000-1000-8000-00805f9b34fb" % val)


class SensorOnOffMixin(object):
    sensorOn = chr(0x01)
    sensorOff = chr(0x00)


class SensorBase(object):

    """Base Class for all Sensirion Sensors."""

    sensorOff = sensorOn = None
    # Derived classes should set: svcUUID, ctrlUUID, dataUUID
    svcUUID = None  # subclass should define
    ctrlUUID = None
    dataUUID = None

    def __init__(self, protocol):
        """Constructor."""
        logging.debug('foo2 %s', self)
        assert self.svcUUID and self.ctrlUUID and self.dataUUID, \
            'subclass defined properties'
        self.protocol = protocol
        self.service = None
        self.ctrl = None
        self.data = None

    def enable(self):
        """Enable sensor."""
        def enable_async(result_, sensor):
            sensor.service = result_
            # if self.ctrl is None:
            #    self.ctrl = self.service.getCharacteristics(self.ctrlUUID)[0]
            if self.data is None:
                self.data = self.service.getCharacteristics(self.dataUUID)[0]
            if self.sensorOn is not None:
                self.ctrl.write(self.sensorOn, withResponse=True)

        # self.protocol.getServiceByUUID(self.svcUUID, enable_async, self)

    def read(self):
        """Read data."""
        if self.data is None:
            return

        return self.data.read()

    def disable(self):
        """Disable sensor."""
        if self.ctrl is not None and self.sensorOff is not None:
            self.ctrl.write(self.sensorOff)

    # Derived class should implement _formatData()


class HumiditySensor(SensorBase):

    """SensorBase SHTC1 RH/Temp sensor."""

    name = 'Sensirion SHTC1 RH/Temp Sensor'

    svcUUID = _TI_UUID(0xAA20)
    dataUUID = _TI_UUID(0xAA21)
    ctrlUUID = _TI_UUID(0xAA22)

    def __init__(self, protocol):
        """Constructor."""
        logging.debug('foo3 %s', self)
        SensorBase.__init__(self, protocol)

    def read(self):
        """Return (ambient_temp, target_temp) in degC."""
        # See
        # http://processors.wiki.ti.com/index.php/SensirionSHTC1_User_Guide#IR_Temperature_Sensor
        temp, humidity = struct.unpack('<hh', self.read())
        # temp = float('%s.%s' % (str(temp)[:2], str(temp)[2:]))
        # humidity = float('%s.%s' % (str(humidity)[:2], str(humidity)[2:]))
        return temp/100, humidity/100


class SensirionSHTC1(Protocol):

    """Sensirion SHTC1."""

    def __init__(self):
        """Constructor."""
        Protocol.__init__(self)
        logging.debug('foo1 %s', self)
        self.sensors = {}

    def add_sensors(self, sensors):
        for sensorCls in sensors:
            self.sensors[sensorCls.name] = sensorCls(self)

    def go(self):
        self.discoverServices()

    def enable(self):
        for sensor in self.sensors.values():
            sensor.enable()

    def disable(self):
        for sensor in self.sensors.values():
            sensor.disable()

    def __repr__(self):
        """Repr for class."""
        ret = '%s@%s' % (self.__class__.__name__, id(self))
        return ret
