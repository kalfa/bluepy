"""Utilities for btle"""

import binascii

BASE_UUID = "00001000800000805F9B34FB"


class UUID:

    """Object representing a UUID"""

    binary = None  # binary form

    def __init__(self, val):
        '''We accept: 32-digit hex strings, with and without '-' characters,
        4 to 8 digit hex strings, and integers'''
        if isinstance(val, int):
            if (val < 0) or (val > 0xFFFFFFFF):
                raise ValueError(
                    "Short form UUIDs must be in range 0..0xFFFFFFFF")
            val = "%04X" % val
        elif isinstance(val, self.__class__):
            # if it's already an instance, normalization and sanity checks have
            # already been perfomed. Set the binary value and return!
            self.binary = val.binary
            return
        else:
            val = str(val)  # Do our best

        # Normalize
        val = val.replace("-", "")
        if len(val) <= 8:  # Short form
            # pad the value and append the base UUID
            val = ("0" * (8 - len(val))) + val + BASE_UUID

        self.binary = binascii.a2b_hex(val)
        if len(self.binary) != 16:
            raise ValueError(
                "UUID must be 16 bytes, got '%s' (len=%d)" % (
                    val, len(self.binary)))

    def __str__(self):
        s = binascii.b2a_hex(self.binary).decode('utf-8')
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:32]])

    def __eq__(self, other):
        return self.binary == UUID(other).binary

    def __cmp__(self, other):
        return cmp(self.binary, UUID(other).binary)

    def __hash__(self):
        return hash(self.binary)
