"""Version 1 vehicle frames: AA 10 02 02 LEFT RIGHT CRC8 55."""
from dataclasses import dataclass


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0x07 if crc & 0x80 else 0)) & 255
    return crc


@dataclass(frozen=True)
class VehiclePacket:
    data: bytes

    @property
    def hex_string(self):
        return self.data.hex(" ").upper()


def build_vehicle_packet(left, right):
    if any(type(v) is not int or not -100 <= v <= 100 for v in (left, right)):
        raise ValueError("Wheel commands must be integers in -100..100")
    body = bytes((0x10, 2, 2, left & 255, right & 255))
    return VehiclePacket(b"\xaa" + body + bytes((crc8(body), 0x55)))
