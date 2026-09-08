"""Jetson 단일 실행 진입점: PC 자동 탐색 후 카메라/AI/UART/H.264 송신을 시작한다."""

import argparse
import signal
import sys

# Jetson에서는 GStreamer가 활성화된 시스템 OpenCV를 우선한다.
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, "/usr/lib/python3.10/dist-packages")

from src.camera.camera_capture import CameraCapture
from src.communication.uart_sender import UartSender
from src.config import (
    CAMERA_INDEX,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DISCOVERY_PORT,
    METADATA_PORT,
    PAN_INITIAL_ANGLE,
    PAN_INVERTED,
    PAN_MAX_ANGLE,
    PAN_MIN_ANGLE,
    SFACE_INTERVAL_FRAMES,
    SFACE_MODEL_PATH,
    SERVO_SEND_INTERVAL_SECONDS,
    STREAM_BITRATE,
    STREAM_HOST,
    STREAM_MTU,
    TARGET_FPS,
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
    VIDEO_PORT,
    YUNET_MODEL_PATH,
    YUNET_NMS_THRESHOLD,
    YUNET_SCORE_THRESHOLD,
    YUNET_TOP_K,
)
from src.detection.yunet_detector import YuNetDetector
from src.network.discovery import discover_pc
from src.recognition.sface_extractor import SFaceExtractor
from src.streaming.gstreamer_sender import GStreamerSender
from src.streaming.metadata import MetadataPublisher
from src.tracking.face_tracker import FaceTracker
from src.workers.vision_processor import VisionProcessor


def resolve_pc_host(manual_host: str | None) -> tuple[str, int, int]:
    """우선순위: --pc-ip > VISION_STREAM_HOST > 자동 검색."""
    if manual_host:
        return manual_host, VIDEO_PORT, METADATA_PORT
    if STREAM_HOST:
        print(f"PC IP 수동 설정 사용: {STREAM_HOST}")
        return STREAM_HOST, VIDEO_PORT, METADATA_PORT

    result = discover_pc(DISCOVERY_PORT)
    print(f"PC 자동 검색 완료: {result.host}")
    return result.host, result.video_port, result.metadata_port


def build_processor(host: str, video_port: int, metadata_port: int) -> VisionProcessor:
    camera = CameraCapture(
        CAMERA_INDEX,
        DEFAULT_FRAME_WIDTH,
        DEFAULT_FRAME_HEIGHT,
        TARGET_FPS,
    )
    detector = YuNetDetector(
        YUNET_MODEL_PATH,
        YUNET_SCORE_THRESHOLD,
        YUNET_NMS_THRESHOLD,
        YUNET_TOP_K,
    )
    extractor = SFaceExtractor(SFACE_MODEL_PATH)
    tracker = FaceTracker(
        PAN_INITIAL_ANGLE,
        TILT_INITIAL_ANGLE,
        (PAN_MIN_ANGLE, PAN_MAX_ANGLE),
        (TILT_MIN_ANGLE, TILT_MAX_ANGLE),
        TRACKING_FILTER_ALPHA,
        TRACKING_DEAD_ZONE_RATIO,
        TRACKING_GAIN,
        TRACKING_MAX_STEP_DEGREES,
        PAN_INVERTED,
        TILT_INVERTED,
    )
    uart = UartSender(UART_PORT, UART_BAUD_RATE, UART_WRITE_TIMEOUT_SECONDS)
    video = GStreamerSender(
        host,
        video_port,
        DEFAULT_FRAME_WIDTH,
        DEFAULT_FRAME_HEIGHT,
        TARGET_FPS,
        STREAM_BITRATE,
        STREAM_MTU,
    )
    metadata = MetadataPublisher(host, metadata_port)
    return VisionProcessor(
        camera,
        detector,
        extractor,
        tracker,
        uart,
        video,
        metadata,
        SERVO_SEND_INTERVAL_SECONDS,
        UART_RETRY_INTERVAL_SECONDS,
        TARGET_FPS,
        SFACE_INTERVAL_FRAMES,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Vision Tracker Jetson runner")
    parser.add_argument(
        "--pc-ip",
        default=None,
        help="자동 검색 대신 사용할 PC IPv4 주소 (예: 192.168.0.12)",
    )
    args = parser.parse_args()

    try:
        host, video_port, metadata_port = resolve_pc_host(args.pc_ip)
        processor = build_processor(host, video_port, metadata_port)
    except Exception as error:
        print(f"Jetson 초기화 오류: {error}", file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, lambda *_: processor.request_stop())
    signal.signal(signal.SIGTERM, lambda *_: processor.request_stop())
    try:
        print(
            "Jetson 시작: "
            f"PC={host}, video={video_port}, metadata={metadata_port}, "
            f"{DEFAULT_FRAME_WIDTH}x{DEFAULT_FRAME_HEIGHT}@{TARGET_FPS}"
        )
        processor.run()
        return 0
    except Exception as error:
        print(f"Jetson 영상 처리 오류: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
