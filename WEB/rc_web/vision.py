"""One camera owner and per-client latest-frame delivery."""
from collections import deque
from dataclasses import asdict
from pathlib import Path
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'AI'))


class VisionService:
    def __init__(self, control_service=None):
        self.control = threading.RLock()
        self.control_service = control_service
        self.condition = threading.Condition()
        self.worker = None
        self.latest = None
        self.sequence = 0
        self.session = uuid.uuid4().hex
        self.samples = deque(maxlen=600)
        self.state = {'error': None, 'mode': 'ai', 'people': [], 'tracking': None,
                      'tracking_enabled': False, 'uart': '대기', 'detector': None,
                      'target': None,
                      'capture_fps': 0.0, 'ai_fps': 0.0, 'processing_ms': 0.0,
                      'frame_age_ms': 0.0, 'inference_frames_skipped': 0}
        self.reports = deque(maxlen=20)

    def update(self, **values):
        with self.condition:
            self.state.update(values)
            self.condition.notify_all()

    def start(self, mode='ai'):
        from src import config as c
        from src.camera.camera_capture import CameraCapture
        from src.communication.uart_sender import UartSender
        from src.detection.person_detector import PersonDetector
        from src.recognition.appearance_reid import AppearanceReIdentifier
        from src.recognition.osnet_reid import OSNetReIdentifier
        from src.tracking.person_tracker import PersonTracker
        from src.workers.video_worker import VideoWorker
        with self.control:
            if self.worker and self.worker.is_alive():
                raise RuntimeError('카메라 OFF 후 모드를 변경하세요.')
            reidentifier = (OSNetReIdentifier(c.PERSON_REID_MODEL_PATH,
                                             c.PERSON_REID_HISTORY_SIZE)
                            if mode == 'ai' else AppearanceReIdentifier())
            detector = PersonDetector(c.PERSON_MODEL_PATH, confidence=c.PERSON_CONFIDENCE,
                                      image_size=c.PERSON_IMAGE_SIZE,
                                      device=c.PERSON_DEVICE) if mode == 'ai' else None
            tracker = PersonTracker(reidentifier,
                reid_interval=c.PERSON_REID_INTERVAL_SECONDS,
                pan_initial=c.PAN_INITIAL_ANGLE, tilt_initial=c.TILT_INITIAL_ANGLE,
                pan_range=(c.PAN_MIN_ANGLE, c.PAN_MAX_ANGLE), tilt_range=(c.TILT_MIN_ANGLE, c.TILT_MAX_ANGLE),
                filter_alpha=c.TRACKING_FILTER_ALPHA,
                gain=c.TRACKING_GAIN, max_step_degrees=c.TRACKING_MAX_STEP_DEGREES,
                box_history_size=c.TRACKING_BOX_HISTORY_SIZE,
                boundary_confirm_frames=c.TRACKING_BOUNDARY_CONFIRM_FRAMES,
                pan_confirm_frames=c.TRACKING_PAN_CONFIRM_FRAMES,
                tilt_confirm_frames=c.TRACKING_TILT_CONFIRM_FRAMES,
                settle_seconds=c.TRACKING_SETTLE_SECONDS,
                pan_start_margin=c.TRACKING_PAN_START_MARGIN,
                pan_release_margin=c.TRACKING_PAN_RELEASE_MARGIN,
                head_box_ratio=c.TRACKING_HEAD_BOX_RATIO,
                head_start_band=(c.TRACKING_HEAD_START_TOP, c.TRACKING_HEAD_START_BOTTOM),
                head_release_band=(c.TRACKING_HEAD_RELEASE_TOP, c.TRACKING_HEAD_RELEASE_BOTTOM),
                predictive_pan_duration=c.TRACKING_PREDICTIVE_PAN_DURATION_SECONDS,
                predictive_pan_max_degrees=c.TRACKING_PREDICTIVE_PAN_MAX_DEGREES,
                predictive_pan_min_speed=c.TRACKING_PREDICTIVE_PAN_MIN_SPEED_PER_SECOND,
                predictive_pan_edge_margin=c.TRACKING_PREDICTIVE_PAN_EDGE_MARGIN,
                predictive_motion_window=c.TRACKING_PREDICTIVE_MOTION_WINDOW_SECONDS,
                pan_inverted=c.PAN_INVERTED, tilt_inverted=c.TILT_INVERTED,
                reid_threshold=c.PERSON_REID_THRESHOLD, reid_margin=c.PERSON_REID_MARGIN,
                lost_timeout=c.PERSON_LOST_TIMEOUT_SECONDS)
            uart_sender = (self.control_service.mailbox if self.control_service is not None else
                           UartSender(c.UART_PORT, c.UART_BAUD_RATE, c.UART_WRITE_TIMEOUT_SECONDS))
            worker = VideoWorker(CameraCapture(c.CAMERA_INDEX, c.DEFAULT_FRAME_WIDTH, c.DEFAULT_FRAME_HEIGHT),
                detector, tracker, uart_sender,
                send_interval=c.SERVO_SEND_INTERVAL_SECONDS, uart_retry_interval=c.UART_RETRY_INTERVAL_SECONDS)
            worker.raw_mode = mode != 'ai'
            # Baseline modes never open UART; AI keeps the existing tracking path.
            worker.uart_enabled = mode == 'ai'
            with self.condition:
                self.latest = None
                self.sequence = 0
                self.session = uuid.uuid4().hex
                self.samples.clear()
                self.state.update(error=None, mode=mode, people=[], tracking=None,
                                  tracking_enabled=False, detector=None, target=None, uart='대기',
                                  capture_fps=0.0, ai_fps=0.0, processing_ms=0.0,
                                  frame_age_ms=0.0, inference_frames_skipped=0)
            worker.camera_opened.connect(lambda info: self.update(camera=asdict(info)))
            worker.people_updated.connect(lambda people: self.update(people=people))
            worker.detector_status_updated.connect(lambda value: self.update(detector=value))
            worker.target_status_updated.connect(lambda value: self.update(target=value))
            worker.capture_fps_updated.connect(lambda fps: self.update(capture_fps=fps))
            worker.fps_updated.connect(lambda fps: self.update(ai_fps=fps))
            worker.processing_updated.connect(self.update_processing)
            worker.tracking_updated.connect(lambda value: self.update(tracking=value))
            worker.uart_status_updated.connect(lambda ok, message: self.update(uart=message))
            worker.error_occurred.connect(lambda message: self.update(error=message))
            worker.capture_stopped.connect(lambda: self.update(tracking_enabled=False))
            worker.frame_ready.connect(self.publish)
            self.worker = worker
            worker.start()

    def stop(self):
        with self.control:
            if self.worker:
                self.worker.set_tracking_enabled(False)
                self.worker.request_stop()
                self.worker.join(5)
                if self.worker.is_alive():
                    raise RuntimeError('카메라 종료 대기 중입니다.')
            self.update(tracking_enabled=False)

    def track(self, enabled):
        with self.control:
            if not self.worker or not self.worker.is_alive() or self.state['mode'] != 'ai':
                raise RuntimeError('AI 모드 카메라를 먼저 시작하세요.')
            self.worker.set_tracking_enabled(enabled)
            self.update(tracking_enabled=enabled)

    def select_target(self, x_ratio, y_ratio):
        with self.control:
            if not self.worker or not self.worker.is_alive() or self.state['mode'] != 'ai':
                raise RuntimeError('AI 모드 카메라를 먼저 시작하세요.')
            selected_id = self.worker.select_target(x_ratio, y_ratio)
            return selected_id

    def clear_target(self):
        with self.control:
            if not self.worker or not self.worker.is_alive() or self.state['mode'] != 'ai':
                raise RuntimeError('AI 모드 카메라를 먼저 시작하세요.')
            self.worker.clear_target()

    def update_processing(self, processing_ms, frame_age_ms, skipped):
        with self.condition:
            self.state['processing_ms'] = processing_ms
            self.state['frame_age_ms'] = frame_age_ms
            self.state['inference_frames_skipped'] += skipped

    def publish(self, frame, captured_at=None):
        import cv2
        start = time.monotonic()
        data = None
        if self.state['mode'] != 'camera':
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise RuntimeError('JPEG 인코딩 실패')
            data = encoded.tobytes()
        now = time.monotonic()
        with self.condition:
            self.sequence += 1
            self.samples.append((now, (now-start)*1000, len(data or b'')))
            if data:
                self.latest = (self.sequence, now, data)
            self.condition.notify_all()
        self.worker.mark_frame_consumed()

    def status(self):
        with self.condition:
            now = time.monotonic()
            samples = [x for x in self.samples if now-x[0] <= 5]
            span = samples[-1][0]-samples[0][0] if len(samples)>1 else 0
            fps = (len(samples)-1)/span if span and self.worker and self.worker.is_alive() else 0
            uart = self.state['uart']
            if self.control_service is not None:
                sender = self.control_service.sender
                if sender is None:
                    uart = '비활성 — UART 포트 미설정'
                elif sender.is_open:
                    uart = f'연결됨 — {sender.port} {sender.baud_rate}bps'
                else:
                    uart = f'재연결 대기 — {sender.port}'
            return {**self.state, 'uart': uart,
                    'running': bool(self.worker and self.worker.is_alive()),
                    'session': self.session, 'sequence': self.sequence, 'server_fps': fps,
                    'jpeg_ms': sum(x[1] for x in samples)/len(samples) if samples else 0,
                    'jpeg_bytes': sum(x[2] for x in samples)/len(samples) if samples else 0,
                    'client_reports': list(self.reports)}

    def frame(self, after=0):
        with self.condition:
            self.condition.wait_for(lambda: (self.latest and self.latest[0] > after)
                                    or not self.worker or not self.worker.is_alive(), timeout=2)
            return self.latest if self.latest and self.latest[0] > after else None
