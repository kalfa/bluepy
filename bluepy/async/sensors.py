"""Sensirion SHTC1 BLE classes."""

import math
import struct
import sys

from btle import UUID, Peripheral

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
    svcUUID = None # subclass should define
    ctrlUUID = None
    dataUUID = None

    def __init__(self, protocol):
        """Constructor."""
        assert self.svcUUID and self.ctrlUUID and self.dataUUID, \
            'subclass defined properties'
        self.protocol = protocol
        self.service = self.protocol.getServiceByUUID(self.svcUUID)
        self.ctrl = None
        self.data = None

    def enable(self):
        """Enable sensor."""
        #if self.ctrl is None:
        #    self.ctrl = self.service.getCharacteristics(self.ctrlUUID)[0]
        if self.data is None:
            self.data = self.service.getCharacteristics(self.dataUUID)[0]
        if self.sensorOn is not None:
            self.ctrl.write(self.sensorOn, withResponse=True)

    def read(self):
        """Read data."""
        return self.data.read()

    def disable(self):
        """Disable sensor."""
        if self.ctrl is not None:
            self.ctrl.write(self.sensorOff)

    # Derived class should implement _formatData()


class HumiditySensor(SensorBase):

    """SensorBase SHTC1 RH/Temp sensor."""

    name = 'Sensirion SHTC1 RH/Temp Sensor'

    svcUUID = _TI_UUID(0xAA20)
    dataUUID = _TI_UUID(0xAA21)
    ctrlUUID = _TI_UUID(0xAA22)

    def __init__(self, periph):
        """Constructor."""
        SensorBase.__init__(self, periph)

    def read(self):
        """Return (ambient_temp, target_temp) in degC."""
        # See
        # http://processors.wiki.ti.com/index.php/SensirionSHTC1_User_Guide#IR_Temperature_Sensor
        temp, humidity = struct.unpack('<hh', self.read())
        #temp = float('%s.%s' % (str(temp)[:2], str(temp)[2:]))
        #humidity = float('%s.%s' % (str(humidity)[:2], str(humidity)[2:]))
        return temp/100, humidity/100


class SensirionSHTC1(Protocol):

    """Sensirion SHTC1."""

    def __init__(self, addr, sensors=None):
        """Constructor."""
        Protocol.__init__(self, addr)

        self.discoverServices()
        self.sensors = {}
        for sensorCls in sensors:
            self.sensors[sensorCls.name] = sensorCls(self)

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
        while True:
            for device in devices:
                for sensor in device.sensors.values():
                    print('%s(%s): %s' % (sensor.name,
                                          sensor.periph.deviceAddr,
                                          sensor.read()))
            time.sleep(5.0)
    except Exception as e:
        print(e)
        for device in devices:
            print("Disconnecting from %s" % devices)
            device.disconnect()
