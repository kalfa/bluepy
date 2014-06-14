"""Sensirion SHTC1 BLE classes."""

import math
import struct
import sys

from btle import UUID, Peripheral

def _TI_UUID(val):
    """Get TI UUID from short UUID."""
    return UUID("%08X-0000-1000-8000-00805f9b34fb" % val)


class SensorBase(object):

    """Base Class for all Sensirion Sensors."""

    # Derived classes should set: svcUUID, ctrlUUID, dataUUID
    sensorOn = chr(0x01)
    sensorOff = chr(0x00)

    def __init__(self, periph):
        """Constructor."""
        self.periph = periph
        self.service = self.periph.getServiceByUUID(self.svcUUID)
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

    """Humidity sensor."""

    name = 'TempRH'

    sensorOn = sensorOff = None
    svcUUID = _TI_UUID(0xAA20)
    dataUUID = _TI_UUID(0xAA21)
    ctrlUUID = _TI_UUID(0xAA22)

    def __init__(self, periph):
        """Constructor."""
        SensorBase.__init__(self, periph)

    def read(self):
        """Return (ambient_temp, rel_humidity)."""
        (rawT, rawH) = struct.unpack('<HH', self.data.read())
        temp = -46.85 + 175.72 * (rawT / 65536.0)
        RH = -6.0 + 125.0 * ((rawH & 0xFFFC)/65536.0)
        return (temp, RH)

    def read(self):
        """Return (ambient_temp, target_temp) in degC."""
        # See
        # http://processors.wiki.ti.com/index.php/SensirionSHTC1_User_Guide#IR_Temperature_Sensor
        data = SensorBase.read(self)
        temp, humidity = struct.unpack('<hh', data)
        temp = float('%s.%s' % (str(temp)[:2], str(temp)[2:]))
        humidity = float('%s.%s' % (str(humidity)[:2], str(humidity)[2:]))
        return temp, humidity



class SensirionSHTC1(Peripheral):

    """Sensirion SHTC1."""

    def __init__(self, addr, sensors=None):
        """Constructor."""
        Peripheral.__init__(self, addr)

        self.discoverServices()
        self.sensors = {}
        for sensorCls in sensors:
            self.sensors[sensorCls.name] = sensorCls(self)

    def __repr__(self):
        """Repr for class."""
        ret = '<%s@%s: %s / %s>' % (self.__class__, id(self),
                                    self.services, self.sensors.keys())
        return ret

if __name__ == "__main__":
    import time

    def quickTest(sensor):
        """self test."""
        sensor.enable()
        for _ in range(10):
            print("Result", sensor.read())
            time.sleep(1.0)
        sensor.disable()


    devices = [SensirionSHTC1(addr, sensors=(HumiditySensor,))
               for addr in sys.argv[1:]]
    try:
        for device in devices:
            for s in device.sensors.values():
                s.enable()

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
