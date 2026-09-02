"""애플리케이션 기본 설정."""

from pathlib import Path


CAMERA_INDEX = 0
DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480
WINDOW_TITLE = "Jetson Vision Tracker - YuNet + SFace"

AI_ROOT = Path(__file__).resolve().parents[1]
YUNET_MODEL_PATH = AI_ROOT / "models" / "face_detection_yunet_2023mar.onnx"
YUNET_SCORE_THRESHOLD = 0.8
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5000

SFACE_MODEL_PATH = AI_ROOT / "models" / "face_recognition_sface_2021dec.onnx"
