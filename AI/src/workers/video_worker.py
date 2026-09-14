"""카메라 캡처와 사람 검출을 분리한 최신 프레임 작업자."""

from collections import deque
import threading
import time

from src.workers.events import Event
from src.camera.camera_capture import CameraCapture, CameraError
from src.communication.protocol import build_servo_packet
from src.communication.uart_sender import UartError, UartSender
from src.config import PAN_TARGET_ID, TILT_TARGET_ID
from src.detection.person_detector import PersonDetectorError


class VideoWorker(threading.Thread):
    """카메라는 계속 읽고 AI는 가장 최신 프레임만 처리한다."""

    def __init__(self, camera: CameraCapture, detector, tracker,
                 uart_sender: UartSender,
                 send_interval: float = 0.1,
                 uart_retry_interval: float = 2.0) -> None:
        super().__init__(daemon=True)
        self.frame_ready = Event()
        self.camera_opened = Event()
        self.fps_updated = Event()
        self.capture_fps_updated = Event()
        self.processing_updated = Event()
        self.people_updated = Event()
        self.detector_status_updated = Event()
        self.target_status_updated = Event()
        self.tracking_updated = Event()
        self.uart_status_updated = Event()
        self.error_occurred = Event()
        self.capture_stopped = Event()
        self.uart_enabled = True
        self.raw_mode = False
        self.camera = camera
        self.detector = detector
        self.tracker = tracker
        self.uart_sender = uart_sender
        self.send_interval = send_interval
        self.uart_retry_interval = uart_retry_interval
        self._stop_event = threading.Event()
        self._tracking_enabled = threading.Event()
        self._latest_condition = threading.Condition()
        self._latest_frame = None
        self._capture_sequence = 0
        self._capture_error = None
        self._capture_finished = False

    def request_stop(self) -> None:
        self._stop_event.set()
        with self._latest_condition:
            self._latest_condition.notify_all()

    @property
    def is_tracking_enabled(self) -> bool:
        return self._tracking_enabled.is_set()

    def set_tracking_enabled(self, enabled: bool) -> None:
        (self._tracking_enabled.set if enabled else self._tracking_enabled.clear)()

    def select_target(self, x_ratio, y_ratio):
        return self.tracker.select_at(x_ratio, y_ratio)

    def clear_target(self):
        self.tracker.clear_selection()

    def mark_frame_consumed(self) -> None:
        """이전 소비자 API와의 호환을 위한 no-op."""

    def _capture_loop(self) -> None:
        timestamps = deque()
        last_emit = 0.0
        try:
            while not self._stop_event.is_set():
                frame = self.camera.read()
                captured_at = time.monotonic()
                with self._latest_condition:
                    self._capture_sequence += 1
                    self._latest_frame = self._capture_sequence, captured_at, frame
                    self._latest_condition.notify()
                timestamps.append(captured_at)
                while timestamps and captured_at - timestamps[0] > 1.0:
                    timestamps.popleft()
                if captured_at - last_emit >= 0.5:
                    self.capture_fps_updated.emit(float(len(timestamps)))
                    last_emit = captured_at
        except Exception as error:
            with self._latest_condition:
                self._capture_error = error
                self._latest_condition.notify_all()
        finally:
            with self._latest_condition:
                self._capture_finished = True
                self._latest_condition.notify_all()

    def _next_latest(self, processed_sequence):
        with self._latest_condition:
            self._latest_condition.wait_for(
                lambda: self._stop_event.is_set() or self._capture_error is not None
                or self._capture_finished or self._capture_sequence > processed_sequence,
                timeout=1.0,
            )
            if self._capture_error is not None:
                raise self._capture_error
            if self._stop_event.is_set():
                return None
            if self._capture_sequence <= processed_sequence:
                return None if self._capture_finished else ()
            sequence, captured_at, frame = self._latest_frame
            return sequence, captured_at, frame.copy()

    def run(self) -> None:
        output_timestamps = deque()
        capture_thread = None
        processed_sequence = 0
        last_fps_emit = 0.0
        last_servo_send = 0.0
        next_uart_retry = 0.0
        try:
            info = self.camera.open()
            self.camera_opened.emit(info)
            capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            capture_thread.start()

            while not self._stop_event.is_set():
                latest = self._next_latest(processed_sequence)
                if latest is None:
                    break
                if latest == ():
                    continue
                sequence, captured_at, frame = latest
                skipped = max(0, sequence - processed_sequence - 1) if processed_sequence else 0
                processed_sequence = sequence
                started_at = time.monotonic()

                if self.uart_enabled and not self.uart_sender.is_open and started_at >= next_uart_retry:
                    try:
                        self.uart_sender.open()
                        self.uart_status_updated.emit(
                            True, f"연결됨 — {self.uart_sender.port} {self.uart_sender.baud_rate}bps"
                        )
                    except UartError as error:
                        self.uart_status_updated.emit(False, str(error))
                        next_uart_retry = started_at + self.uart_retry_interval

                detections = [] if self.raw_mode else self.detector.detect(frame)
                height, width = frame.shape[:2]
                tracking_enabled = self.is_tracking_enabled
                tracking = None
                send_due = started_at - last_servo_send >= self.send_interval
                if not self.raw_mode:
                    tracking = self.tracker.update(
                        detections, frame, (width, height),
                        move_servos=tracking_enabled,
                        control_step_due=(
                            tracking_enabled and self.uart_sender.is_open and send_due
                        ),
                    )

                if tracking_enabled and tracking is not None:
                    pan_packet = build_servo_packet(PAN_TARGET_ID, tracking.pan_angle)
                    tilt_packet = build_servo_packet(TILT_TARGET_ID, tracking.tilt_angle)
                    sent = False
                    if self.uart_sender.is_open and send_due and tracking.angles_changed:
                        try:
                            self.uart_sender.send((pan_packet, tilt_packet))
                            last_servo_send = started_at
                            sent = True
                        except UartError as error:
                            self.uart_status_updated.emit(False, str(error))
                            next_uart_retry = started_at + self.uart_retry_interval
                    self.tracking_updated.emit({
                        "center": tracking.center,
                        "pan_angle": tracking.pan_angle,
                        "tilt_angle": tracking.tilt_angle,
                        "pan_packet": pan_packet.hex_string,
                        "tilt_packet": tilt_packet.hex_string,
                        "sent": sent,
                        "target_id": tracking.target.track_id,
                        "aim_source": tracking.aim_source,
                    })
                else:
                    self.tracking_updated.emit(None)

                selected_id = self.tracker.selected_id if self.tracker is not None else None
                if self.detector is not None:
                    self.detector.draw(frame, detections, selected_id)
                if self.tracker is not None:
                    self.tracker.draw(frame, tracking)
                self.people_updated.emit([{
                    "track_id": person.track_id,
                    "box": list(person.box),
                    "confidence": person.confidence,
                    "reid_similarity": person.reid_similarity,
                    "selected": person.track_id == selected_id,
                } for person in detections])
                self.detector_status_updated.emit({
                    "inference_ms": self.detector.elapsed_ms if self.detector else 0.0,
                    "model": getattr(self.detector, "model_name", "YOLO Person") if self.detector else None,
                })
                self.target_status_updated.emit(self.tracker.status() if self.tracker else None)
                self.frame_ready.emit(frame, captured_at)

                completed_at = time.monotonic()
                self.processing_updated.emit(
                    (completed_at - started_at) * 1000.0,
                    (completed_at - captured_at) * 1000.0,
                    skipped,
                )
                output_timestamps.append(completed_at)
                while output_timestamps and completed_at - output_timestamps[0] > 1.0:
                    output_timestamps.popleft()
                if completed_at - last_fps_emit >= 0.5:
                    self.fps_updated.emit(float(len(output_timestamps)))
                    last_fps_emit = completed_at
        except (CameraError, PersonDetectorError) as error:
            self.error_occurred.emit(str(error))
        except Exception as error:
            self.error_occurred.emit(f"예상하지 못한 영상 처리 오류: {error}")
        finally:
            self._stop_event.set()
            if capture_thread is not None:
                capture_thread.join(2)
            self.uart_sender.close()
            self.camera.release()
            if self.detector is not None and hasattr(self.detector, "close"):
                self.detector.close()
            if self.tracker is not None and hasattr(self.tracker, "close"):
                self.tracker.close()
            self.capture_stopped.emit()
