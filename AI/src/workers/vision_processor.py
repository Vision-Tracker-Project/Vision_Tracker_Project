"""Qt/X11과 독립적으로 실행되는 Jetson 영상 처리 및 UART 제어 루프."""

from collections import deque
import threading
import time
import uuid
from src.camera.camera_capture import CameraError
from src.communication.protocol import build_servo_packet
from src.communication.uart_sender import UartError
from src.config import PAN_TARGET_ID, TILT_TARGET_ID
from src.streaming.metadata import StreamMetadata

class VisionProcessor:
    def __init__(self, camera, detector, extractor, tracker, uart_sender, video_publisher,
                 metadata_publisher, send_interval=0.1, uart_retry_interval=2.0,
                 target_fps=20, sface_interval=5) -> None:
        self.camera, self.detector, self.extractor = camera, detector, extractor
        self.tracker, self.uart_sender = tracker, uart_sender
        self.video_publisher, self.metadata_publisher = video_publisher, metadata_publisher
        self.send_interval, self.uart_retry_interval = send_interval, uart_retry_interval
        self.target_fps = max(1, target_fps)
        self.sface_interval = max(1, sface_interval)
        self.stop_event = threading.Event()
        self.session_id = uuid.uuid4().hex
        self.sequence = 0

    def request_stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        timestamps = deque()
        last_servo_send = 0.0
        next_uart_retry = 0.0
        has_sent_angles = False
        uart_message = "연결 대기"
        try:
            self.camera.open()
            self.video_publisher.start()
            while not self.stop_event.is_set():
                loop_started = time.monotonic()
                t0 = time.perf_counter()
                frame = self.camera.read()
                t1 = time.perf_counter()
                now = time.monotonic()
                if not self.uart_sender.is_open and now >= next_uart_retry:
                    try:
                        self.uart_sender.open()
                        uart_message, has_sent_angles = "연결됨", False
                    except UartError as error:
                        uart_message = str(error)
                        next_uart_retry = now + self.uart_retry_interval

                detections = self.detector.detect(frame)
                t2 = time.perf_counter()
                # 인식은 추적 대상 한 명만 주기 처리해 제어 루프의 20 FPS를 우선한다.
                if detections and self.sequence % self.sface_interval == 0:
                    target = max(detections, key=lambda item: item.box[2] * item.box[3])
                    self.extractor.extract(frame, target)
                t3 = time.perf_counter()
                height, width = frame.shape[:2]
                tracking = self.tracker.update(detections, (width, height))
                t4 = time.perf_counter()
                tracking_data = None
                if tracking is not None:
                    pan_packet = build_servo_packet(PAN_TARGET_ID, tracking.pan_angle)
                    tilt_packet = build_servo_packet(TILT_TARGET_ID, tracking.tilt_angle)
                    sent = False
                    if self.uart_sender.is_open and now - last_servo_send >= self.send_interval and (
                        tracking.angles_changed or not has_sent_angles
                    ):
                        try:
                            self.uart_sender.send((pan_packet, tilt_packet))
                            last_servo_send, has_sent_angles, sent = now, True, True
                        except UartError as error:
                            uart_message = str(error)
                            next_uart_retry, has_sent_angles = now + self.uart_retry_interval, False
                    tracking_data = {
                        "center": list(tracking.center), "pan_angle": tracking.pan_angle,
                        "tilt_angle": tracking.tilt_angle, "pan_packet": pan_packet.hex_string,
                        "tilt_packet": tilt_packet.hex_string, "sent": sent,
                    }

                self.detector.draw(frame, detections)
                self.tracker.draw(frame, tracking)
                self.video_publisher.publish(frame)
                
                t5 = time.perf_counter()
                timestamps.append(now)
                while timestamps and now - timestamps[0] > 1.0:
                    timestamps.popleft()
                fps = float(len(timestamps))
                self.metadata_publisher.publish(StreamMetadata(
                    session_id=self.session_id, sequence=self.sequence,
                    source_time=time.time(), processing_fps=fps,
                    face_count=len(detections), tracking=tracking_data,
                    uart={"connected": self.uart_sender.is_open, "message": uart_message},
                ))
                t6 = time.perf_counter()
                self.sequence += 1
                remaining = 1.0 / self.target_fps - (time.monotonic() - loop_started)
                if remaining > 0:
                    self.stop_event.wait(remaining)
        finally:
            self.video_publisher.close()
            self.metadata_publisher.close()
            self.uart_sender.close()
            self.camera.release()
