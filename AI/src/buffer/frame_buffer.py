"""시간 기준으로 오래된 JPEG 프레임을 제거하는 순환 버퍼."""

from collections import deque
from dataclasses import dataclass
import threading
from typing import Deque, Optional, Tuple


@dataclass(frozen=True)
class BufferedFrame:
    """압축 프레임과 촬영 시각."""

    timestamp: float
    jpeg_data: bytes


class FrameBuffer:
    """최근 일정 시간의 JPEG 프레임을 메모리에 보관."""

    def __init__(self, max_duration_seconds: float = 60.0) -> None:
        if max_duration_seconds <= 0.0:
            raise ValueError("버퍼 시간은 0보다 커야 합니다.")
        self.max_duration_seconds = max_duration_seconds
        self._frames: Deque[BufferedFrame] = deque()
        self._lock = threading.Lock()

    def append(self, timestamp: float, jpeg_data: bytes) -> None:
        if not jpeg_data:
            raise ValueError("JPEG 데이터가 비어 있습니다.")
        with self._lock:
            if self._frames and timestamp < self._frames[-1].timestamp:
                raise ValueError("프레임 시각은 이전 프레임보다 빠를 수 없습니다.")
            self._frames.append(BufferedFrame(timestamp, jpeg_data))
            cutoff = timestamp - self.max_duration_seconds
            while self._frames and self._frames[0].timestamp < cutoff:
                self._frames.popleft()

    def closest(self, timestamp: float) -> Optional[BufferedFrame]:
        """요청 시각과 가장 가까운 프레임 반환."""
        with self._lock:
            if not self._frames:
                return None
            return min(self._frames, key=lambda item: abs(item.timestamp - timestamp))

    def bounds(self) -> Optional[Tuple[float, float]]:
        with self._lock:
            if not self._frames:
                return None
            return self._frames[0].timestamp, self._frames[-1].timestamp

    def stats(self) -> Tuple[int, float, int]:
        """프레임 수, 보관 시간, JPEG 총용량 반환."""
        with self._lock:
            if not self._frames:
                return 0, 0.0, 0
            duration = self._frames[-1].timestamp - self._frames[0].timestamp
            total_bytes = sum(len(item.jpeg_data) for item in self._frames)
            return len(self._frames), duration, total_bytes

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
