from .utils import UUID


class BTLEException(Exception):

    """BTLE Exception."""

    DISCONNECTED = 1
    COMM_ERROR = 2
    INTERNAL_ERROR = 3

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


class AssignedNumbers:
    # TODO: full list
    deviceName = UUID("2A00")
    txPowerLevel = UUID("2A07")
    batteryLevel = UUID("2A19")
    modelNumberString = UUID("2A24")
    serialNumberString = UUID("2A25")
    firmwareRevisionString = UUID("2A26")
    hardwareRevisionString = UUID("2A27")
    softwareRevisionString = UUID("2A28")
    manufacturerNameString = UUID("2A29")

    nameMap = {
        deviceName: "Device Name",
        txPowerLevel: "Tx Power Level",
        batteryLevel: "Battery Level",
        modelNumberString: "Model Number String",
        serialNumberString: "Serial Number String",
        firmwareRevisionString: "Firmware Revision String",
        hardwareRevisionString: "Hardware Revision String",
        softwareRevisionString: "Software Revision String",
        manufacturerNameString: "Manufacturer Name String",
    }

    @staticmethod
    def getCommonName(uuid):
        return AssignedNumbers.nameMap.get(uuid, None)
