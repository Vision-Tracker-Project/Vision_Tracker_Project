"""PC에서 실행되는 Jetson 네트워크 영상 GUI."""

import cv2
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
from src.config import (
    DEFAULT_FRAME_HEIGHT, DEFAULT_FRAME_WIDTH, METADATA_PORT, METADATA_STALE_SECONDS,
    PAN_INITIAL_ANGLE, STREAM_BIND_ADDRESS, TILT_INITIAL_ANGLE, VIDEO_PORT, WINDOW_TITLE,
)
from src.streaming.stream_receiver import MetadataReceiver, VideoReceiver

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.video_receiver = None
        self.metadata_receiver = None
        self._last_image = None
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(50)
        self.frame_timer.timeout.connect(self._poll_frame)
        self.setWindowTitle(WINDOW_TITLE + " — PC Client")
        self.resize(1100, 760)
        self._build_ui()
        self._set_running_state(False)
        # main.py 실행만으로 영상/메타데이터 수신을 시작한다.
        QTimer.singleShot(0, self.start_camera)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.video_label = QLabel("Jetson 자동 연결 대기 중...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet("background-color:#151515;color:#dddddd;")
        layout.addWidget(self.video_label, stretch=1)
        status = QHBoxLayout()
        self.status_label = QLabel("상태: 정지됨")
        self.face_count_label = QLabel("검출 얼굴: 0")
        self.embedding_label = QLabel("처리 FPS: 0.0")
        self.fps_label = QLabel("표시 FPS: 0.0")
        for widget in (self.status_label, self.face_count_label, self.embedding_label, self.fps_label):
            status.addWidget(widget)
        layout.addLayout(status)
        tracking = QHBoxLayout()
        self.tracking_label = QLabel("추적: 얼굴 대기")
        self.servo_label = QLabel(f"팬 {PAN_INITIAL_ANGLE}° / 틸트 {TILT_INITIAL_ANGLE}°")
        self.uart_label = QLabel("UART: Jetson 상태 대기")
        tracking.addWidget(self.tracking_label)
        tracking.addWidget(self.servo_label)
        tracking.addWidget(self.uart_label)
        layout.addLayout(tracking)
        self.packet_label = QLabel("패킷: 대기")
        layout.addWidget(self.packet_label)
        controls = QHBoxLayout()
        controls.addStretch()
        self.start_button = QPushButton("영상 수신 ON")
        self.stop_button = QPushButton("영상 수신 OFF")
        self.exit_button = QPushButton("종료")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.exit_button.clicked.connect(self.close)
        for widget in (self.start_button, self.stop_button, self.exit_button):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self.setCentralWidget(central)

    def start_camera(self) -> None:
        if self.video_receiver and self.video_receiver.isRunning():
            return
        self.video_receiver = VideoReceiver(
            VIDEO_PORT, DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT, self
        )
        self.metadata_receiver = MetadataReceiver(
            STREAM_BIND_ADDRESS, METADATA_PORT, METADATA_STALE_SECONDS, self
        )
        self.video_receiver.fps_updated.connect(
            lambda fps: self.fps_label.setText(f"표시 FPS: {fps:.1f}")
        )
        self.video_receiver.connection_changed.connect(self._connection_changed)
        self.metadata_receiver.connection_changed.connect(self._connection_changed)
        self.metadata_receiver.metadata_ready.connect(self._display_metadata)
        self.video_receiver.start()
        self.metadata_receiver.start()
        self.status_label.setText("상태: Jetson 연결 대기...")
        self.frame_timer.start()
        self._set_running_state(True)

    def stop_camera(self) -> None:
        self.frame_timer.stop()
        if self.video_receiver and self.video_receiver.isRunning():
            self.video_receiver.stop()
            self.video_receiver.wait(2000)
        if self.metadata_receiver and self.metadata_receiver.isRunning():
            self.metadata_receiver.requestInterruption()
            self.metadata_receiver.wait(1000)
        self.video_receiver = self.metadata_receiver = None
        self.status_label.setText("상태: 정지됨")
        self._set_running_state(False)

    def _poll_frame(self) -> None:
        if self.video_receiver:
            frame = self.video_receiver.take_latest()
            if frame is not None:
                self._display_frame(frame)

    def _connection_changed(self, connected: bool, message: str) -> None:
        self.status_label.setText(f"상태: {message}")

    def _display_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        self._last_image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
        self._render_last_image()

    def _display_metadata(self, item) -> None:
        self.face_count_label.setText(f"검출 얼굴: {item.face_count}")
        self.embedding_label.setText(f"처리 FPS: {item.processing_fps:.1f}")
        uart = item.uart
        self.uart_label.setText(f"UART {'연결' if uart.get('connected') else '오류'}: {uart.get('message', '')}")
        tracking = item.tracking
        if not tracking:
            self.tracking_label.setText("추적: 얼굴 대기")
            return
        center = tracking.get("center", [0, 0])
        self.tracking_label.setText(f"추적 중심: ({center[0]:.0f}, {center[1]:.0f})")
        self.servo_label.setText(f"팬 {tracking.get('pan_angle', 0)}° / 틸트 {tracking.get('tilt_angle', 0)}°")
        self.packet_label.setText(
            f"PAN: {tracking.get('pan_packet', '-')}    TILT: {tracking.get('tilt_packet', '-')}"
        )

    def _render_last_image(self) -> None:
        if self._last_image is not None:
            pixmap = QPixmap.fromImage(self._last_image).scaled(
                self.video_label.size(), Qt.KeepAspectRatio, Qt.FastTransformation
            )
            self.video_label.setPixmap(pixmap)

    def _set_running_state(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_last_image()

    def closeEvent(self, event) -> None:
        self.stop_camera()
        event.accept()
