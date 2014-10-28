import time
import sys

from bluepy.async.sensors import SensirionSHTC1, HumiditySensor


if __name__ == "__main__":
    addr = sys.argv[1]
    transport = transport.Transport()
    device = SensirionSHTC1()

    try:
        device.add_sensors((HumiditySensor,))
        device.init(transport)
        transport.connect(addr)

        for s in device.sensors.values():
            s.enable()

        while True:
            for sensor in device.sensors.values():
                print('%s(%s): %s' % (sensor.name,
                                    sensor.protocol.deviceAddr,
                                    sensor.read()))
            time.sleep(5.0)
    except Exception as e:
        print(e)
        for device in devices:
            print("Disconnecting from %s" % devices)
            device.close()
