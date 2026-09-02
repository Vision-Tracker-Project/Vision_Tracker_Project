"""USB 카메라 미리보기 메인 창."""

import cv2
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
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
from src.capture.frame_capture import CaptureError, FrameCapture
from src.communication.uart_sender import UartSender
from src.config import (
    CAMERA_INDEX,
    CAPTURE_DEFAULT_DIR,
    CAPTURE_FLASH_MILLISECONDS,
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
    VIDEO_STYLE = (
        "background-color: #151515; color: #dddddd; "
        "border: 3px solid #151515; border-radius: 8px; font-size: 16px;"
    )
    CAPTURE_FLASH_STYLE = (
        "background-color: #151515; color: #dddddd; "
        "border: 3px solid #ffd400; border-radius: 8px; font-size: 16px;"
    )

    def __init__(self) -> None:
        super().__init__()
        self.worker = None
        self._latest_live_image = None
        self._displayed_image = None
        self._latest_live_frame = None
        self._displayed_frame = None
        self._is_replay_mode = False
        self.frame_capture = FrameCapture(CAPTURE_DEFAULT_DIR)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 820)
        self.setMinimumSize(1000, 700)
        self._apply_theme()
        self._build_ui()
        self._capture_flash_timer = QTimer(self)
        self._capture_flash_timer.setSingleShot(True)
        self._capture_flash_timer.timeout.connect(self._restore_video_border)
        self.frame_buffer_worker = FrameBufferWorker(
            max_duration_seconds=REPLAY_BUFFER_SECONDS,
            jpeg_quality=REPLAY_JPEG_QUALITY,
            parent=self,
        )
        self.frame_buffer_worker.buffer_updated.connect(self._on_buffer_updated)
        self.frame_buffer_worker.error_occurred.connect(self._on_buffer_error)
        self.frame_buffer_worker.start()
        self._set_running_state(False)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget#centralWidget {
                background-color: #eef2f6;
            }
            QWidget {
                color: #1f2937;
                font-size: 13px;
            }
            QLabel#titleLabel {
                color: #102a43;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #627d98;
                font-size: 13px;
            }
            QLabel#primaryStatus {
                background-color: #e8f1fb;
                border: 1px solid #bfd7ee;
                border-radius: 7px;
                color: #174a72;
                font-weight: 600;
                padding: 10px;
            }
            QLabel#metricLabel {
                background-color: #f5f8fb;
                border: 1px solid #d9e2ec;
                border-radius: 7px;
                font-weight: 600;
                padding: 9px;
            }
            QLabel#mutedLabel {
                color: #627d98;
            }
            QLabel#pathLabel {
                background-color: #f5f8fb;
                border-radius: 6px;
                color: #486581;
                padding: 7px;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                margin-top: 12px;
                padding: 16px 12px 12px 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #334e68;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #bcccdc;
                border-radius: 7px;
                min-height: 38px;
                padding: 0 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f0f4f8;
                border-color: #829ab1;
            }
            QPushButton:pressed {
                background-color: #d9e2ec;
            }
            QPushButton:disabled {
                background-color: #e7edf3;
                border-color: #d9e2ec;
                color: #9fb3c8;
            }
            QPushButton#startButton, QPushButton#captureButton {
                background-color: #167d5a;
                border-color: #167d5a;
                color: #ffffff;
            }
            QPushButton#startButton:hover, QPushButton#captureButton:hover {
                background-color: #116149;
            }
            QPushButton#stopButton {
                background-color: #d97706;
                border-color: #d97706;
                color: #ffffff;
            }
            QPushButton#stopButton:hover {
                background-color: #b45309;
            }
            QPushButton#liveButton {
                background-color: #2563a6;
                border-color: #2563a6;
                color: #ffffff;
            }
            QPushButton#liveButton:hover {
                background-color: #1d4f85;
            }
            QPushButton#exitButton {
                background-color: #b42318;
                border-color: #b42318;
                color: #ffffff;
            }
            QPushButton#exitButton:hover {
                background-color: #8f1c13;
            }
            QPushButton#startButton:disabled,
            QPushButton#stopButton:disabled,
            QPushButton#captureButton:disabled,
            QPushButton#liveButton:disabled,
            QPushButton#exitButton:disabled {
                background-color: #e7edf3;
                border-color: #d9e2ec;
                color: #9fb3c8;
            }
            QSlider::groove:horizontal {
                background: #d9e2ec;
                border-radius: 3px;
                height: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82b8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #2563a6;
                border-radius: 9px;
                height: 18px;
                margin: -7px 0;
                width: 18px;
            }
            QSlider::handle:horizontal:hover {
                background: #dbeafe;
            }
            QSlider::groove:horizontal:disabled {
                background: #e7edf3;
            }
            QSlider::handle:horizontal:disabled {
                background: #e7edf3;
                border-color: #bcccdc;
            }
            """
        )

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(18, 14, 18, 18)
        root_layout.setSpacing(12)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        title_label = QLabel("Vision Tracker")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel(
            "USB 카메라 · YuNet 얼굴 검출 · SFace 특징 추출 · 팬틸트 추적"
        )
        subtitle_label.setObjectName("subtitleLabel")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        root_layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(10)

        self.video_label = QLabel("카메라 시작 버튼을 누르세요.")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet(self.VIDEO_STYLE)
        video_layout.addWidget(self.video_label, stretch=1)

        replay_group = QGroupBox("최근 60초 다시보기")
        replay_group_layout = QVBoxLayout(replay_group)
        replay_group_layout.setSpacing(8)
        timeline_layout = QHBoxLayout()
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.setTracking(True)
        self.timeline_slider.sliderPressed.connect(self._begin_replay)
        self.timeline_slider.valueChanged.connect(self._on_timeline_changed)
        past_label = QLabel("60초 전")
        past_label.setObjectName("mutedLabel")
        current_label = QLabel("현재")
        current_label.setObjectName("mutedLabel")
        timeline_layout.addWidget(past_label)
        timeline_layout.addWidget(self.timeline_slider, stretch=1)
        timeline_layout.addWidget(current_label)
        replay_group_layout.addLayout(timeline_layout)

        replay_action_layout = QHBoxLayout()
        self.replay_status_label = QLabel("다시보기: 버퍼 대기")
        self.replay_status_label.setObjectName("mutedLabel")
        self.live_button = QPushButton("실시간 복귀")
        self.live_button.setObjectName("liveButton")
        self.live_button.setEnabled(False)
        self.live_button.clicked.connect(self._return_to_live)
        replay_action_layout.addWidget(self.replay_status_label, stretch=1)
        replay_action_layout.addWidget(self.live_button)
        replay_group_layout.addLayout(replay_action_layout)
        video_layout.addWidget(replay_group)

        capture_group = QGroupBox("화면 캡처")
        capture_group_layout = QVBoxLayout(capture_group)
        capture_action_layout = QHBoxLayout()
        self.capture_button = QPushButton("현재 화면 캡처")
        self.capture_button.setObjectName("captureButton")
        self.capture_button.setEnabled(False)
        self.capture_button.clicked.connect(self.capture_current_frame)
        self.capture_directory_button = QPushButton("저장 폴더 선택")
        self.capture_directory_button.clicked.connect(self.select_capture_directory)
        self.capture_status_label = QLabel("캡처: 대기")
        self.capture_status_label.setObjectName("mutedLabel")
        capture_action_layout.addWidget(self.capture_button)
        capture_action_layout.addWidget(self.capture_directory_button)
        capture_action_layout.addWidget(self.capture_status_label, stretch=1)
        capture_group_layout.addLayout(capture_action_layout)

        self.capture_directory_label = QLabel(str(self.frame_capture.output_directory))
        self.capture_directory_label.setObjectName("pathLabel")
        self.capture_directory_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.capture_directory_label.setWordWrap(True)
        capture_group_layout.addWidget(self.capture_directory_label)
        video_layout.addWidget(capture_group)

        content_layout.addWidget(video_panel, stretch=1)

        sidebar = QWidget()
        sidebar.setMinimumWidth(320)
        sidebar.setMaximumWidth(370)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        camera_group = QGroupBox("카메라 및 AI 상태")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setSpacing(8)
        self.status_label = QLabel("상태: 정지됨")
        self.status_label.setObjectName("primaryStatus")
        self.status_label.setWordWrap(True)
        self.face_count_label = QLabel("검출 얼굴: 0")
        self.face_count_label.setObjectName("metricLabel")
        self.embedding_label = QLabel("SFace: 대기")
        self.embedding_label.setWordWrap(True)
        self.fps_label = QLabel("출력 FPS: 0.0")
        self.fps_label.setObjectName("metricLabel")
        camera_layout.addWidget(self.status_label)
        metric_layout = QGridLayout()
        metric_layout.setHorizontalSpacing(8)
        metric_layout.addWidget(self.face_count_label, 0, 0)
        metric_layout.addWidget(self.fps_label, 0, 1)
        metric_layout.setColumnStretch(0, 1)
        metric_layout.setColumnStretch(1, 1)
        camera_layout.addLayout(metric_layout)
        camera_layout.addWidget(self.embedding_label)
        sidebar_layout.addWidget(camera_group)

        tracking_group = QGroupBox("팬·틸트 추적")
        tracking_layout = QVBoxLayout(tracking_group)
        tracking_layout.setSpacing(8)
        self.tracking_label = QLabel("추적: 얼굴 대기")
        self.tracking_label.setWordWrap(True)
        self.servo_label = QLabel(
            f"팬 {PAN_INITIAL_ANGLE}° / 틸트 {TILT_INITIAL_ANGLE}°"
        )
        self.servo_label.setObjectName("metricLabel")
        self.uart_label = QLabel(f"UART: 대기 — {UART_PORT}")
        self.uart_label.setWordWrap(True)
        self.packet_label = QLabel("패킷: 대기")
        self.packet_label.setObjectName("pathLabel")
        self.packet_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.packet_label.setWordWrap(True)
        tracking_layout.addWidget(self.tracking_label)
        tracking_layout.addWidget(self.servo_label)
        tracking_layout.addWidget(self.uart_label)
        tracking_layout.addWidget(self.packet_label)
        sidebar_layout.addWidget(tracking_group)

        control_group = QGroupBox("카메라 제어")
        control_layout = QVBoxLayout(control_group)
        camera_button_layout = QHBoxLayout()

        self.start_button = QPushButton("카메라 ON")
        self.start_button.setObjectName("startButton")
        self.stop_button = QPushButton("카메라 OFF")
        self.stop_button.setObjectName("stopButton")
        self.exit_button = QPushButton("종료")
        self.exit_button.setObjectName("exitButton")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.exit_button.clicked.connect(self.close)
        camera_button_layout.addWidget(self.start_button)
        camera_button_layout.addWidget(self.stop_button)
        control_layout.addLayout(camera_button_layout)
        control_layout.addWidget(self.exit_button)
        sidebar_layout.addWidget(control_group)
        sidebar_layout.addStretch()

        content_layout.addWidget(sidebar)
        root_layout.addLayout(content_layout, stretch=1)
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
            self._latest_live_frame = frame.copy()
            self._latest_live_image = self._frame_to_image(self._latest_live_frame)
            if not self._is_replay_mode:
                self._displayed_frame = self._latest_live_frame
                self._displayed_image = self._latest_live_image
                self._render_displayed_image()
            self.capture_button.setEnabled(True)
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
        self._displayed_frame = frame
        self._displayed_image = self._frame_to_image(self._displayed_frame)
        self._render_displayed_image()
        self.replay_status_label.setText(f"다시보기: -{seconds_ago:.1f}초")

    def _return_to_live(self) -> None:
        self._is_replay_mode = False
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(0)
        self.timeline_slider.blockSignals(False)
        self.live_button.setEnabled(False)
        if self._latest_live_image is not None:
            self._displayed_frame = self._latest_live_frame
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

    def select_capture_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "캡처 저장 폴더 선택",
            str(self.frame_capture.output_directory),
        )
        if not selected:
            return
        try:
            self.frame_capture.set_output_directory(selected)
        except CaptureError as error:
            self.capture_status_label.setText(f"캡처 오류: {error}")
            return
        self.capture_directory_label.setText(str(self.frame_capture.output_directory))
        self.capture_status_label.setText("캡처: 저장 폴더 변경")

    def capture_current_frame(self) -> None:
        source = "replay" if self._is_replay_mode else "live"
        try:
            output_path = self.frame_capture.save(self._displayed_frame, source)
        except CaptureError as error:
            self.capture_status_label.setText(f"캡처 오류: {error}")
            return
        self.capture_status_label.setText(f"캡처 완료: {output_path.name}")
        self.video_label.setStyleSheet(self.CAPTURE_FLASH_STYLE)
        self._capture_flash_timer.start(CAPTURE_FLASH_MILLISECONDS)

    def _restore_video_border(self) -> None:
        self.video_label.setStyleSheet(self.VIDEO_STYLE)

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
