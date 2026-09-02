"""GUI 스레드 밖에서 카메라 프레임을 읽는 QThread 작업자."""

from collections import deque
import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from src.camera.camera_capture import CameraCapture, CameraError


class VideoWorker(QThread):
    """최신 카메라 프레임과 실제 전달 FPS를 Signal로 전송한다."""

    frame_ready = pyqtSignal(object)
    camera_opened = pyqtSignal(object)
    fps_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    capture_stopped = pyqtSignal()

    def __init__(self, camera: CameraCapture, parent=None) -> None:
        super().__init__(parent)
        self.camera = camera
        self._stop_event = threading.Event()
        self._pending_lock = threading.Lock()
        self._frame_pending = False

    def request_stop(self) -> None:
        self._stop_event.set()
        self.requestInterruption()

    def mark_frame_consumed(self) -> None:
        """GUI가 표시를 끝냈음을 기록해 다음 프레임 전달을 허용한다."""
        with self._pending_lock:
            self._frame_pending = False

    def _reserve_frame_signal(self) -> bool:
        with self._pending_lock:
            if self._frame_pending:
                return False
            self._frame_pending = True
            return True

    def run(self) -> None:
        output_timestamps = deque()
        last_fps_emit = 0.0
        try:
            info = self.camera.open()
            self.camera_opened.emit(info)

            while not self._stop_event.is_set() and not self.isInterruptionRequested():
                frame = self.camera.read()
                now = time.monotonic()

                # 아직 GUI가 이전 프레임을 처리 중이면 새 프레임을 버린다.
                if self._reserve_frame_signal():
                    self.frame_ready.emit(frame)
                    output_timestamps.append(now)
                    while output_timestamps and now - output_timestamps[0] > 1.0:
                        output_timestamps.popleft()

                if now - last_fps_emit >= 0.5:
                    fps = float(len(output_timestamps)) if len(output_timestamps) > 1 else 0.0
                    self.fps_updated.emit(fps)
                    last_fps_emit = now
        except CameraError as error:
            self.error_occurred.emit(str(error))
        except Exception as error:
            self.error_occurred.emit(f"예상하지 못한 카메라 오류: {error}")
        finally:
            self.camera.release()
            self.capture_stopped.emit()
