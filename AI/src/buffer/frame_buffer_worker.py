"""GUI와 영상 처리 스레드를 막지 않고 프레임을 JPEG로 압축."""

import threading
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from src.buffer.frame_buffer import FrameBuffer


class FrameBufferWorker(QThread):
    """가장 최근에 제출된 프레임만 압축해 순환 버퍼에 저장."""

    buffer_updated = pyqtSignal(float, int, int)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        max_duration_seconds: float = 60.0,
        jpeg_quality: int = 80,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("JPEG 품질은 1~100 범위여야 합니다.")
        self.buffer = FrameBuffer(max_duration_seconds)
        self.jpeg_quality = jpeg_quality
        self._condition = threading.Condition()
        self._pending: Optional[Tuple[int, float, np.ndarray]] = None
        self._stop_requested = False
        self._generation = 0

    def submit(self, frame: np.ndarray, timestamp: float) -> None:
        """압축 대기 중인 이전 프레임을 최신 프레임으로 교체."""
        with self._condition:
            if self._stop_requested:
                return
            self._pending = (self._generation, timestamp, frame.copy())
            self._condition.notify()

    def request_stop(self) -> None:
        with self._condition:
            self._stop_requested = True
            self._pending = None
            self._condition.notify_all()
        self.requestInterruption()

    def clear(self) -> None:
        with self._condition:
            self._generation += 1
            self._pending = None
        self.buffer.clear()
        self.buffer_updated.emit(0.0, 0, 0)

    def frame_seconds_ago(self, seconds_ago: float) -> Optional[np.ndarray]:
        """최신 시각 기준 과거 JPEG 프레임 복원."""
        bounds = self.buffer.bounds()
        if bounds is None:
            return None
        _, latest = bounds
        item = self.buffer.closest(latest - max(0.0, seconds_ago))
        if item is None:
            return None
        encoded = np.frombuffer(item.jpeg_data, dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    def run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._stop_requested:
                    self._condition.wait()
                if self._stop_requested:
                    return
                generation, timestamp, frame = self._pending
                self._pending = None

            try:
                success, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
                )
                if not success:
                    raise RuntimeError("JPEG 인코딩 결과가 비어 있습니다.")
                with self._condition:
                    if generation != self._generation:
                        continue
                    self.buffer.append(timestamp, encoded.tobytes())
                count, duration, total_bytes = self.buffer.stats()
                self.buffer_updated.emit(duration, count, total_bytes)
            except Exception as error:
                self.error_occurred.emit(f"프레임 버퍼 저장 실패: {error}")
