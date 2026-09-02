"""USB 카메라 미리보기 메인 창."""

import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.camera.camera_capture import CameraCapture
from src.config import (
    CAMERA_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    WINDOW_TITLE,
    YUNET_MODEL_PATH,
    YUNET_NMS_THRESHOLD,
    YUNET_SCORE_THRESHOLD,
    YUNET_TOP_K,
)
from src.detection.yunet_detector import YuNetDetector, YuNetError
from src.workers.video_worker import VideoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker = None
        self._last_image = None
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1100, 760)
        self._build_ui()
        self._set_running_state(False)

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)

        self.video_label = QLabel("카메라 시작 버튼을 누르세요.")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet("background-color: #151515; color: #dddddd;")
        layout.addWidget(self.video_label, stretch=1)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("상태: 정지됨")
        self.face_count_label = QLabel("검출 얼굴: 0")
        self.fps_label = QLabel("출력 FPS: 0.0")
        status_layout.addWidget(self.status_label, stretch=1)
        status_layout.addWidget(self.face_count_label)
        status_layout.addWidget(self.fps_label)
        layout.addLayout(status_layout)

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

        try:
            detector = YuNetDetector(
                model_path=YUNET_MODEL_PATH,
                score_threshold=YUNET_SCORE_THRESHOLD,
                nms_threshold=YUNET_NMS_THRESHOLD,
                top_k=YUNET_TOP_K,
            )
        except YuNetError as error:
            self._on_camera_error(str(error))
            return

        camera = CameraCapture(
            camera_index=CAMERA_INDEX,
            width=DEFAULT_FRAME_WIDTH,
            height=DEFAULT_FRAME_HEIGHT,
        )
        self.worker = VideoWorker(camera, detector, self)
        self.worker.frame_ready.connect(self._display_frame)
        self.worker.camera_opened.connect(self._on_camera_opened)
        self.worker.fps_updated.connect(self._on_fps_updated)
        self.worker.face_count_updated.connect(self._on_face_count_updated)
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
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb_frame.shape
            self._last_image = QImage(
                rgb_frame.data,
                width,
                height,
                channels * width,
                QImage.Format_RGB888,
            ).copy()
            self._render_last_image()
        finally:
            if self.worker is not None:
                self.worker.mark_frame_consumed()

    def _render_last_image(self) -> None:
        if self._last_image is None:
            return
        pixmap = QPixmap.fromImage(self._last_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self.video_label.setPixmap(pixmap)

    def _on_fps_updated(self, fps: float) -> None:
        self.fps_label.setText(f"출력 FPS: {fps:.1f}")

    def _on_face_count_updated(self, count: int) -> None:
        self.face_count_label.setText(f"검출 얼굴: {count}")

    def _on_camera_error(self, message: str) -> None:
        self.status_label.setText(f"상태: 오류 — {message}")
        self.video_label.setText(message)

    def _on_capture_stopped(self) -> None:
        if not self.status_label.text().startswith("상태: 오류"):
            self.status_label.setText("상태: 정지됨")
        self.face_count_label.setText("검출 얼굴: 0")
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
        self._render_last_image()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            if not self.worker.wait(3000):
                self.status_label.setText("상태: 카메라 스레드가 종료될 때까지 기다리는 중...")
                event.ignore()
                return
        event.accept()
