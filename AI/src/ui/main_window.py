"""USB 카메라 미리보기 메인 창."""

import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.buffer.frame_buffer_worker import FrameBufferWorker
from src.camera.camera_capture import CameraCapture
from src.communication.uart_sender import UartSender
from src.config import (
    CAMERA_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    PAN_INITIAL_ANGLE,
    PAN_INVERTED,
    PAN_MAX_ANGLE,
    PAN_MIN_ANGLE,
    REPLAY_BUFFER_SECONDS,
    REPLAY_JPEG_QUALITY,
    SERVO_SEND_INTERVAL_SECONDS,
    SFACE_MODEL_PATH,
    TILT_INITIAL_ANGLE,
    TILT_INVERTED,
    TILT_MAX_ANGLE,
    TILT_MIN_ANGLE,
    TRACKING_DEAD_ZONE_RATIO,
    TRACKING_FILTER_ALPHA,
    TRACKING_GAIN,
    TRACKING_MAX_STEP_DEGREES,
    UART_BAUD_RATE,
    UART_PORT,
    UART_RETRY_INTERVAL_SECONDS,
    UART_WRITE_TIMEOUT_SECONDS,
    WINDOW_TITLE,
    YUNET_MODEL_PATH,
    YUNET_NMS_THRESHOLD,
    YUNET_SCORE_THRESHOLD,
    YUNET_TOP_K,
)
from src.detection.yunet_detector import YuNetDetector, YuNetError
from src.recognition.sface_extractor import SFaceError, SFaceExtractor
from src.tracking.face_tracker import FaceTracker
from src.workers.video_worker import VideoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker = None
        self._latest_live_image = None
        self._displayed_image = None
        self._is_replay_mode = False
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1100, 760)
        self._build_ui()
        self.frame_buffer_worker = FrameBufferWorker(
            max_duration_seconds=REPLAY_BUFFER_SECONDS,
            jpeg_quality=REPLAY_JPEG_QUALITY,
            parent=self,
        )
        self.frame_buffer_worker.buffer_updated.connect(self._on_buffer_updated)
        self.frame_buffer_worker.error_occurred.connect(self._on_buffer_error)
        self.frame_buffer_worker.start()
        self._set_running_state(False)

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)

        self.video_label = QLabel("카메라 시작 버튼을 누르세요.")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet("background-color: #151515; color: #dddddd;")
        layout.addWidget(self.video_label, stretch=1)

        replay_layout = QHBoxLayout()
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.setTracking(True)
        self.timeline_slider.sliderPressed.connect(self._begin_replay)
        self.timeline_slider.valueChanged.connect(self._on_timeline_changed)
        self.replay_status_label = QLabel("다시보기: 버퍼 대기")
        self.live_button = QPushButton("실시간 복귀")
        self.live_button.setEnabled(False)
        self.live_button.clicked.connect(self._return_to_live)
        replay_layout.addWidget(QLabel("-60초"))
        replay_layout.addWidget(self.timeline_slider, stretch=1)
        replay_layout.addWidget(QLabel("현재"))
        replay_layout.addWidget(self.replay_status_label)
        replay_layout.addWidget(self.live_button)
        layout.addLayout(replay_layout)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("상태: 정지됨")
        self.face_count_label = QLabel("검출 얼굴: 0")
        self.embedding_label = QLabel("SFace: 대기")
        self.fps_label = QLabel("출력 FPS: 0.0")
        status_layout.addWidget(self.status_label, stretch=1)
        status_layout.addWidget(self.face_count_label)
        status_layout.addWidget(self.embedding_label)
        status_layout.addWidget(self.fps_label)
        layout.addLayout(status_layout)

        tracking_layout = QHBoxLayout()
        self.tracking_label = QLabel("추적: 얼굴 대기")
        self.servo_label = QLabel(
            f"팬 {PAN_INITIAL_ANGLE}° / 틸트 {TILT_INITIAL_ANGLE}°"
        )
        self.uart_label = QLabel(f"UART: 대기 — {UART_PORT}")
        tracking_layout.addWidget(self.tracking_label, stretch=1)
        tracking_layout.addWidget(self.servo_label)
        tracking_layout.addWidget(self.uart_label)
        layout.addLayout(tracking_layout)

        self.packet_label = QLabel("패킷: 대기")
        self.packet_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.packet_label)

        controls = QHBoxLayout()
        controls.addStretch()

        self.start_button = QPushButton("카메라 ON")
        self.stop_button = QPushButton("카메라 OFF")
        self.exit_button = QPushButton("종료")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.exit_button.clicked.connect(self.close)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.exit_button)
        layout.addLayout(controls)
        self.setCentralWidget(central_widget)

    def start_camera(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        self._return_to_live()
        self.frame_buffer_worker.clear()

        try:
            detector = YuNetDetector(
                model_path=YUNET_MODEL_PATH,
                score_threshold=YUNET_SCORE_THRESHOLD,
                nms_threshold=YUNET_NMS_THRESHOLD,
                top_k=YUNET_TOP_K,
            )
            extractor = SFaceExtractor(model_path=SFACE_MODEL_PATH)
        except (YuNetError, SFaceError) as error:
            self._on_camera_error(str(error))
            return

        camera = CameraCapture(
            camera_index=CAMERA_INDEX,
            width=DEFAULT_FRAME_WIDTH,
            height=DEFAULT_FRAME_HEIGHT,
        )
        tracker = FaceTracker(
            pan_initial=PAN_INITIAL_ANGLE,
            tilt_initial=TILT_INITIAL_ANGLE,
            pan_range=(PAN_MIN_ANGLE, PAN_MAX_ANGLE),
            tilt_range=(TILT_MIN_ANGLE, TILT_MAX_ANGLE),
            filter_alpha=TRACKING_FILTER_ALPHA,
            dead_zone_ratio=TRACKING_DEAD_ZONE_RATIO,
            gain=TRACKING_GAIN,
            max_step_degrees=TRACKING_MAX_STEP_DEGREES,
            pan_inverted=PAN_INVERTED,
            tilt_inverted=TILT_INVERTED,
        )
        uart_sender = UartSender(
            port=UART_PORT,
            baud_rate=UART_BAUD_RATE,
            write_timeout=UART_WRITE_TIMEOUT_SECONDS,
        )
        self.worker = VideoWorker(
            camera,
            detector,
            extractor,
            tracker,
            uart_sender,
            frame_sink=self.frame_buffer_worker,
            send_interval=SERVO_SEND_INTERVAL_SECONDS,
            uart_retry_interval=UART_RETRY_INTERVAL_SECONDS,
            parent=self,
        )
        self.worker.frame_ready.connect(self._display_frame)
        self.worker.camera_opened.connect(self._on_camera_opened)
        self.worker.fps_updated.connect(self._on_fps_updated)
        self.worker.face_count_updated.connect(self._on_face_count_updated)
        self.worker.embedding_status_updated.connect(self._on_embedding_status_updated)
        self.worker.tracking_updated.connect(self._on_tracking_updated)
        self.worker.uart_status_updated.connect(self._on_uart_status_updated)
        self.worker.error_occurred.connect(self._on_camera_error)
        self.worker.capture_stopped.connect(self._on_capture_stopped)
        self.worker.finished.connect(self._on_worker_finished)

        self.status_label.setText("상태: 카메라 연결 중...")
        self._set_running_state(True)
        self.worker.start()

    def stop_camera(self) -> None:
        if self.worker is None:
            self._on_capture_stopped()
            return
        self.status_label.setText("상태: 정지 중...")
        self.worker.request_stop()

    def _on_camera_opened(self, info) -> None:
        self.status_label.setText(
            f"상태: 연결됨 — {info.width}×{info.height}, "
            f"장치 FPS {info.fps:.1f}, {info.backend}"
        )

    def _display_frame(self, frame) -> None:
        try:
            self._latest_live_image = self._frame_to_image(frame)
            if not self._is_replay_mode:
                self._displayed_image = self._latest_live_image
                self._render_displayed_image()
        finally:
            if self.worker is not None:
                self.worker.mark_frame_consumed()

    @staticmethod
    def _frame_to_image(frame) -> QImage:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        return QImage(
            rgb_frame.data,
            width,
            height,
            channels * width,
            QImage.Format_RGB888,
        ).copy()

    def _render_displayed_image(self) -> None:
        if self._displayed_image is None:
            return
        pixmap = QPixmap.fromImage(self._displayed_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self.video_label.setPixmap(pixmap)

    def _begin_replay(self) -> None:
        self._is_replay_mode = True
        self.live_button.setEnabled(True)

    def _on_timeline_changed(self, value: int) -> None:
        if value == 0 and not self._is_replay_mode:
            return
        if value < 0:
            self._is_replay_mode = True
            self.live_button.setEnabled(True)

        seconds_ago = max(0.0, -value / 1000.0)
        frame = self.frame_buffer_worker.frame_seconds_ago(seconds_ago)
        if frame is None:
            return
        self._displayed_image = self._frame_to_image(frame)
        self._render_displayed_image()
        self.replay_status_label.setText(f"다시보기: -{seconds_ago:.1f}초")

    def _return_to_live(self) -> None:
        self._is_replay_mode = False
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(0)
        self.timeline_slider.blockSignals(False)
        self.live_button.setEnabled(False)
        if self._latest_live_image is not None:
            self._displayed_image = self._latest_live_image
            self._render_displayed_image()
        self.replay_status_label.setText("다시보기: 실시간")

    def _on_buffer_updated(
        self, duration_seconds: float, frame_count: int, total_bytes: int
    ) -> None:
        available_ms = min(
            round(REPLAY_BUFFER_SECONDS * 1000), round(duration_seconds * 1000)
        )
        self.timeline_slider.setMinimum(-available_ms)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setEnabled(frame_count > 1)
        if not self._is_replay_mode:
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(0)
            self.timeline_slider.blockSignals(False)
            self.replay_status_label.setText(
                f"다시보기: 실시간 / {duration_seconds:.1f}초 / "
                f"{frame_count}프레임 / {total_bytes / 1024 / 1024:.1f}MB"
            )

    def _on_buffer_error(self, message: str) -> None:
        self.replay_status_label.setText(f"다시보기 오류: {message}")

    def _on_fps_updated(self, fps: float) -> None:
        self.fps_label.setText(f"출력 FPS: {fps:.1f}")

    def _on_face_count_updated(self, count: int) -> None:
        self.face_count_label.setText(f"검출 얼굴: {count}")

    def _on_embedding_status_updated(
        self, count: int, dimension: int, l2_norm: float, elapsed_ms: float
    ) -> None:
        if count == 0:
            self.embedding_label.setText("SFace: 얼굴 대기")
            return
        self.embedding_label.setText(
            f"SFace: OK {count}명 / {dimension}D / "
            f"Norm {l2_norm:.2f} / {elapsed_ms:.1f}ms"
        )

    def _on_tracking_updated(self, tracking) -> None:
        if tracking is None:
            self.tracking_label.setText("추적: 얼굴 대기")
            return
        center_x, center_y = tracking["center"]
        sent_text = "전송" if tracking["sent"] else "유지"
        self.tracking_label.setText(
            f"추적 중심: ({center_x:.0f}, {center_y:.0f}) — {sent_text}"
        )
        self.servo_label.setText(
            f"팬 {tracking['pan_angle']}° / 틸트 {tracking['tilt_angle']}°"
        )
        self.packet_label.setText(
            f"PAN: {tracking['pan_packet']}    "
            f"TILT: {tracking['tilt_packet']}"
        )

    def _on_uart_status_updated(self, connected: bool, message: str) -> None:
        state = "연결" if connected else "오류"
        self.uart_label.setText(f"UART {state}: {message}")

    def _on_camera_error(self, message: str) -> None:
        self.status_label.setText(f"상태: 오류 — {message}")
        self.video_label.setText(message)

    def _on_capture_stopped(self) -> None:
        if not self.status_label.text().startswith("상태: 오류"):
            self.status_label.setText("상태: 정지됨")
        self.face_count_label.setText("검출 얼굴: 0")
        self.embedding_label.setText("SFace: 대기")
        self.tracking_label.setText("추적: 얼굴 대기")
        self.servo_label.setText(
            f"팬 {PAN_INITIAL_ANGLE}° / 틸트 {TILT_INITIAL_ANGLE}°"
        )
        self.uart_label.setText(f"UART: 대기 — {UART_PORT}")
        self.packet_label.setText("패킷: 대기")
        self.fps_label.setText("출력 FPS: 0.0")
        self._set_running_state(False)

    def _on_worker_finished(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        self._set_running_state(False)

    def _set_running_state(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_displayed_image()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            if not self.worker.wait(3000):
                self.status_label.setText("상태: 카메라 스레드가 종료될 때까지 기다리는 중...")
                event.ignore()
                return
        if self.frame_buffer_worker.isRunning():
            self.frame_buffer_worker.request_stop()
            if not self.frame_buffer_worker.wait(3000):
                self.status_label.setText("상태: 버퍼 스레드가 종료될 때까지 기다리는 중...")
                event.ignore()
                return
        event.accept()
