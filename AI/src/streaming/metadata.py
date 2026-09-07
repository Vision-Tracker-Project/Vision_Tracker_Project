"""버전이 지정된 UDP 상태 메시지 송수신."""

from dataclasses import asdict, dataclass
import json
import math
import socket
from typing import Any, Dict, Optional

SCHEMA_VERSION = 1
MAX_DATAGRAM_SIZE = 16 * 1024

class MetadataError(ValueError):
    """상태 메시지가 유효하지 않을 때 발생한다."""

@dataclass(frozen=True)
class StreamMetadata:
    session_id: str
    sequence: int
    source_time: float
    processing_fps: float
    face_count: int
    tracking: Optional[Dict[str, Any]]
    uart: Dict[str, Any]
    schema_version: int = SCHEMA_VERSION

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_bytes(cls, payload: bytes) -> "StreamMetadata":
        if len(payload) > MAX_DATAGRAM_SIZE:
            raise MetadataError("메타데이터 패킷이 너무 큽니다.")
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MetadataError("올바른 JSON 패킷이 아닙니다.") from error
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            raise MetadataError("지원하지 않는 메타데이터 버전입니다.")
        required = ("session_id", "sequence", "source_time", "processing_fps", "face_count", "uart")
        if any(key not in value for key in required):
            raise MetadataError("필수 메타데이터 필드가 누락되었습니다.")
        if not isinstance(value["session_id"], str) or not value["session_id"]:
            raise MetadataError("session_id가 유효하지 않습니다.")
        if not isinstance(value["sequence"], int) or value["sequence"] < 0:
            raise MetadataError("sequence가 유효하지 않습니다.")
        for key in ("source_time", "processing_fps"):
            if not isinstance(value[key], (int, float)) or not math.isfinite(value[key]):
                raise MetadataError(f"{key}가 유효하지 않습니다.")
        if not isinstance(value["face_count"], int) or value["face_count"] < 0:
            raise MetadataError("face_count가 유효하지 않습니다.")
        if not isinstance(value["uart"], dict):
            raise MetadataError("uart가 유효하지 않습니다.")
        tracking = value.get("tracking")
        if tracking is not None and not isinstance(tracking, dict):
            raise MetadataError("tracking이 유효하지 않습니다.")
        connected = value["uart"].get("connected")
        message = value["uart"].get("message", "")
        if type(connected) is not bool or not isinstance(message, str):
            raise MetadataError("uart 내부 필드가 유효하지 않습니다.")
        if tracking is not None:
            center = tracking.get("center")
            if not isinstance(center, list) or len(center) != 2:
                raise MetadataError("tracking.center가 유효하지 않습니다.")
            if any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(item)
                for item in center
            ):
                raise MetadataError("tracking.center 좌표가 유효하지 않습니다.")
            for key in ("pan_angle", "tilt_angle"):
                if type(tracking.get(key)) is not int or not 0 <= tracking[key] <= 180:
                    raise MetadataError(f"tracking.{key}이 유효하지 않습니다.")
        return cls(
            session_id=value["session_id"], sequence=value["sequence"],
            source_time=float(value["source_time"]),
            processing_fps=float(value["processing_fps"]),
            face_count=value["face_count"], tracking=tracking, uart=value["uart"],
        )

class MetadataPublisher:
    def __init__(self, host: str, port: int) -> None:
        self.address = (host, port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)
        self.dropped = 0

    def publish(self, metadata: StreamMetadata) -> None:
        try:
            self._socket.sendto(metadata.to_bytes(), self.address)
        except (BlockingIOError, OSError):
            self.dropped += 1

    def close(self) -> None:
        self._socket.close()

class MetadataOrder:
    """세션별 최신 패킷만 허용한다."""

    def __init__(self) -> None:
        self.session_id: Optional[str] = None
        self.sequence = -1

    def accept(self, item: StreamMetadata) -> bool:
        if item.session_id != self.session_id:
            self.session_id, self.sequence = item.session_id, item.sequence
            return True
        if item.sequence <= self.sequence:
            return False
        self.sequence = item.sequence
        return True
