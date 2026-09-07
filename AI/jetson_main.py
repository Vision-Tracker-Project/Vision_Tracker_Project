"""Jetson headless 실행 진입점: DISPLAY와 PyQt가 필요하지 않다."""

import signal
import sys
# GStreamer가 활성화된 Jetson 시스템 OpenCV를 사용자 설치본보다 우선한다.
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, "/usr/lib/python3.10/dist-packages")
from src.camera.camera_capture import CameraCapture
from src.communication.uart_sender import UartSender
from src.config import *
from src.detection.yunet_detector import YuNetDetector
from src.recognition.sface_extractor import SFaceExtractor
from src.streaming.gstreamer_sender import GStreamerSender
from src.streaming.metadata import MetadataPublisher
from src.tracking.face_tracker import FaceTracker
from src.workers.vision_processor import VisionProcessor

def build_processor() -> VisionProcessor:
    camera = CameraCapture(CAMERA_INDEX, DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT)
    detector = YuNetDetector(YUNET_MODEL_PATH, YUNET_SCORE_THRESHOLD, YUNET_NMS_THRESHOLD, YUNET_TOP_K)
    extractor = SFaceExtractor(SFACE_MODEL_PATH)
    tracker = FaceTracker(
        PAN_INITIAL_ANGLE, TILT_INITIAL_ANGLE,
        (PAN_MIN_ANGLE, PAN_MAX_ANGLE), (TILT_MIN_ANGLE, TILT_MAX_ANGLE),
        TRACKING_FILTER_ALPHA, TRACKING_DEAD_ZONE_RATIO, TRACKING_GAIN,
        TRACKING_MAX_STEP_DEGREES, PAN_INVERTED, TILT_INVERTED,
    )
    uart = UartSender(UART_PORT, UART_BAUD_RATE, UART_WRITE_TIMEOUT_SECONDS)
    video = GStreamerSender(
        STREAM_HOST, VIDEO_PORT, DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT,
        TARGET_FPS, STREAM_BITRATE, STREAM_MTU,
    )
    metadata = MetadataPublisher(STREAM_HOST, METADATA_PORT)
    return VisionProcessor(
        camera, detector, extractor, tracker, uart, video, metadata,
        SERVO_SEND_INTERVAL_SECONDS, UART_RETRY_INTERVAL_SECONDS, TARGET_FPS, SFACE_INTERVAL_FRAMES,
    )

def main() -> int:
    processor = build_processor()
    signal.signal(signal.SIGINT, lambda *_: processor.request_stop())
    signal.signal(signal.SIGTERM, lambda *_: processor.request_stop())
    try:
        print(f"Jetson headless 시작: {STREAM_HOST}, {DEFAULT_FRAME_WIDTH}x{DEFAULT_FRAME_HEIGHT}@{TARGET_FPS}")
        processor.run()
        return 0
    except Exception as error:
        print(f"Jetson 영상 처리 오류: {error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
