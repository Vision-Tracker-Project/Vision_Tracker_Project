"""GUI 스레드 밖에서 카메라 프레임을 읽는 QThread 작업자."""

from collections import deque
import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal

from src.camera.camera_capture import CameraCapture, CameraError
from src.communication.protocol import build_servo_packet
from src.communication.uart_sender import UartError, UartSender
from src.config import PAN_TARGET_ID, TILT_TARGET_ID
from src.detection.yunet_detector import YuNetDetector, YuNetError
from src.recognition.sface_extractor import SFaceError, SFaceExtractor
from src.tracking.face_tracker import FaceTracker


class VideoWorker(QThread):
    """최신 카메라 프레임과 실제 전달 FPS를 Signal로 전송한다."""

    frame_ready = pyqtSignal(object)
    camera_opened = pyqtSignal(object)
    fps_updated = pyqtSignal(float)
    face_count_updated = pyqtSignal(int)
    embedding_status_updated = pyqtSignal(int, int, float, float)
    tracking_updated = pyqtSignal(object)
    uart_status_updated = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)
    capture_stopped = pyqtSignal()

    def __init__(
        self,
        camera: CameraCapture,
        detector: YuNetDetector,
        extractor: SFaceExtractor,
        tracker: FaceTracker,
        uart_sender: UartSender,
        frame_sink=None,
        send_interval: float = 0.1,
        uart_retry_interval: float = 2.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.camera = camera
        self.detector = detector
        self.extractor = extractor
        self.tracker = tracker
        self.uart_sender = uart_sender
        self.frame_sink = frame_sink
        self.send_interval = send_interval
        self.uart_retry_interval = uart_retry_interval
        self._stop_event = threading.Event()
        self._tracking_enabled = threading.Event()
        self._pending_lock = threading.Lock()
        self._frame_pending = False

    def request_stop(self) -> None:
        self._stop_event.set()
        self.requestInterruption()

    @property
    def is_tracking_enabled(self) -> bool:
        return self._tracking_enabled.is_set()

    def set_tracking_enabled(self, enabled: bool) -> None:
        """카메라 처리는 유지하고 각도 계산과 UART 전송만 전환."""
        if enabled:
            self._tracking_enabled.set()
        else:
            self._tracking_enabled.clear()

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
        last_servo_send = 0.0
        next_uart_retry = 0.0
        was_tracking_enabled = False
        try:
            info = self.camera.open()
            self.camera_opened.emit(info)

            while not self._stop_event.is_set() and not self.isInterruptionRequested():
                frame = self.camera.read()
                now = time.monotonic()

                if not self.uart_sender.is_open and now >= next_uart_retry:
                    try:
                        self.uart_sender.open()
                        self.uart_status_updated.emit(
                            True,
                            f"연결됨 — {self.uart_sender.port} "
                            f"{self.uart_sender.baud_rate}bps",
                        )
                    except UartError as error:
                        self.uart_status_updated.emit(False, str(error))
                        next_uart_retry = now + self.uart_retry_interval

                # 아직 GUI가 이전 프레임을 처리 중이면 새 프레임을 버린다.
                if self._reserve_frame_signal():
                    detections = self.detector.detect(frame)
                    embeddings = [
                        self.extractor.extract(frame, detection)
                        for detection in detections
                    ]
                    height, width = frame.shape[:2]
                    tracking_enabled = self.is_tracking_enabled
                    tracking = None
                    if tracking_enabled:
                        if not was_tracking_enabled:
                            self.tracker.reset_target()
                        tracking = self.tracker.update(detections, (width, height))
                        if tracking is None:
                            self.tracking_updated.emit(None)
                        else:
                            pan_packet = build_servo_packet(
                                PAN_TARGET_ID, tracking.pan_angle
                            )
                            tilt_packet = build_servo_packet(
                                TILT_TARGET_ID, tracking.tilt_angle
                            )
                            sent = False
                            send_due = now - last_servo_send >= self.send_interval
                            if (
                                self.uart_sender.is_open
                                and send_due
                                and tracking.angles_changed
                            ):
                                try:
                                    self.uart_sender.send((pan_packet, tilt_packet))
                                    last_servo_send = now
                                    sent = True
                                except UartError as error:
                                    self.uart_status_updated.emit(False, str(error))
                                    next_uart_retry = now + self.uart_retry_interval

                            self.tracking_updated.emit(
                                {
                                    "center": tracking.center,
                                    "pan_angle": tracking.pan_angle,
                                    "tilt_angle": tracking.tilt_angle,
                                    "pan_packet": pan_packet.hex_string,
                                    "tilt_packet": tilt_packet.hex_string,
                                    "sent": sent,
                                }
                            )
                    elif was_tracking_enabled:
                        self.tracker.reset_target()
                    was_tracking_enabled = tracking_enabled
                    self.detector.draw(frame, detections)
                    self.tracker.draw(frame, tracking)
                    self.face_count_updated.emit(len(detections))
                    if embeddings:
                        self.embedding_status_updated.emit(
                            len(embeddings),
                            embeddings[0].dimension,
                            embeddings[0].l2_norm,
                            sum(item.elapsed_ms for item in embeddings),
                        )
                    else:
                        self.embedding_status_updated.emit(0, 0, 0.0, 0.0)
                    if self.frame_sink is not None:
                        self.frame_sink.submit(frame, now)
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
        except YuNetError as error:
            self.error_occurred.emit(str(error))
        except SFaceError as error:
            self.error_occurred.emit(str(error))
        except Exception as error:
            self.error_occurred.emit(f"예상하지 못한 영상 처리 오류: {error}")
        finally:
            self.uart_sender.close()
            self.camera.release()
            self.capture_stopped.emit()
