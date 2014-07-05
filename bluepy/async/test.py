import time
import sys

from bluepy.async.sensors import SensirionSHTC1, HumiditySensor


if __name__ == "__main__":
    devices = []
    for addr in sys.argv[1:]:
        try:
            devices.append(SensirionSHTC1(addr))
            devices[-1].add_sensors((HumiditySensor,))
        except Exception as e:
            print('exception: %s' % e)
            raise

    try:
        for device in devices:
            for s in device.sensors.values():
                s.enable()

        while True:
            for device in devices:
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
