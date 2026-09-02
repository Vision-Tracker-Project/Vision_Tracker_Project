import unittest

from src.communication.protocol import build_servo_packet
from src.communication.uart_sender import UartError, UartSender


class FakeSerial:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.is_open = True
        self.written = bytearray()
        self.flushed = False

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def flush(self):
        self.flushed = True

    def close(self):
        self.is_open = False


class UartProtocolTest(unittest.TestCase):
    def test_builds_exact_six_byte_packet(self):
        packet = build_servo_packet(target_id=0x01, angle=90)

        self.assertEqual(packet.data, bytes([0xAA, 0x01, 0x01, 0x5A, 0x5C, 0x55]))
        self.assertEqual(len(packet.data), 6)
        self.assertEqual(packet.hex_string, "AA 01 01 5A 5C 55")

    def test_rejects_angle_outside_protocol_range(self):
        with self.assertRaisesRegex(ValueError, "0~180"):
            build_servo_packet(target_id=0x01, angle=181)

    def test_sends_pan_and_tilt_as_twelve_bytes(self):
        connection = FakeSerial()

        def serial_factory(**kwargs):
            connection.kwargs = kwargs
            return connection

        sender = UartSender(
            port="/dev/fake",
            serial_factory=serial_factory,
        )
        sender.open()
        pan = build_servo_packet(0x01, 90)
        tilt = build_servo_packet(0x02, 45)

        written = sender.send((pan, tilt))

        self.assertEqual(written, 12)
        self.assertEqual(bytes(connection.written), pan.data + tilt.data)
        self.assertTrue(connection.flushed)
        self.assertEqual(connection.kwargs["bytesize"], 8)
        self.assertEqual(connection.kwargs["parity"], "N")
        self.assertEqual(connection.kwargs["stopbits"], 1)

    def test_send_requires_open_connection(self):
        sender = UartSender(port="/dev/fake", serial_factory=FakeSerial)
        with self.assertRaisesRegex(UartError, "연결되지 않았습니다"):
            sender.send((build_servo_packet(0x01, 90),))


if __name__ == "__main__":
    unittest.main()
