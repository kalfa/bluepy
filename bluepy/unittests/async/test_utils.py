from unittest import TestCase
from bluepy.async.utils import UUID, BASE_UUID


def add_dashes(uuid):
    assert len(uuid) == 32, 'ensure uuid is 32 characters'
    return '%s-%s-%s-%s-%s' % (uuid[:8], uuid[8:12], uuid[12:16],
                               uuid[16:20], uuid[20:32])


class TestPipedFuture(TestCase):
    def test_UUID_as_32_digits_string_is_accepted(self):
        hex_input = '1'*32
        uuid = UUID(hex_input)
        # '11111111-1111-1111-1111-111111111111'
        self.assertEqual(str(uuid), add_dashes(hex_input))

    def test_UUID_as_20_digits_string_not_accepted(self):
        with self.assertRaises(ValueError):
            UUID('1'*20)

    def test_UUID_as_4to8_digits_string_is_accepted(self):
        base_input = '1'*4

        for i in range(5):
            # from four '1' to eight '1'.
            hex_input = base_input +'1'*i
            # Pad shorter inputs, add the base UUID and format with dashes
            padding = '0' * (8 - len(hex_input))
            expected_output = add_dashes(padding + hex_input +
                                         BASE_UUID.lower())
            uuid = UUID(hex_input)
            self.assertEqual(str(uuid), expected_output)

    def test_different_cased_UUID_are_internally_normalized(self):
        upper_hex_input = 'A'*32
        lower_hex_input = 'a'*32

        upper_uuid = UUID(upper_hex_input)
        lower_uuid = UUID(lower_hex_input)

        # Internal representaiton is sane
        self.assertEqual(upper_uuid, lower_uuid)
        # Represent to the same string value
        self.assertEqual(str(upper_uuid), str(lower_uuid))

    def test_uuid_of_uuid_instance_does_not_change_value(self):
        uuid = UUID('1'*4)
        uuid_of_uuid = UUID(uuid)
        self.assertEqual(uuid, uuid_of_uuid)
