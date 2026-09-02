"""STM32 제어용 고정 6바이트 패킷 생성."""

from dataclasses import dataclass

from src.config import PACKET_HEADER, PACKET_TAIL, SET_ANGLE_ACTION


@dataclass(frozen=True)
class ServoPacket:
    """전송 바이트와 화면 표시용 Hex 문자열."""

    target_id: int
    angle: int
    data: bytes

    @property
    def hex_string(self) -> str:
        return " ".join(f"{value:02X}" for value in self.data)


def build_servo_packet(target_id: int, angle: int) -> ServoPacket:
    """HEADER, TARGET, ACTION, PARAM, CHECKSUM, TAIL 순서의 패킷 생성."""
    if not 0 <= target_id <= 0xFF:
        raise ValueError("TARGET_ID는 0x00~0xFF 범위여야 합니다.")
    if not 0 <= angle <= 180:
        raise ValueError("서보 각도는 0~180도 범위여야 합니다.")

    checksum = (target_id + SET_ANGLE_ACTION + angle) & 0xFF
    data = bytes(
        [
            PACKET_HEADER,
            target_id,
            SET_ANGLE_ACTION,
            angle,
            checksum,
            PACKET_TAIL,
        ]
    )
    return ServoPacket(target_id=target_id, angle=angle, data=data)
