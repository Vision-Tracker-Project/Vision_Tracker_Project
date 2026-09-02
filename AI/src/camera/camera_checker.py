"""Linux에서 사용 가능한 USB 카메라 번호를 확인하는 독립 모듈."""

from dataclasses import dataclass
from glob import glob
import re
from typing import List

import cv2


@dataclass(frozen=True)
class CameraCheckResult:
    index: int
    device_path: str
    available: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0
    backend: str = ""
    error: str = ""


def find_camera_indices() -> List[int]:
    """`/dev/videoN` 장치에서 카메라 번호 N을 정렬해 반환한다."""
    indices = []
    for device_path in glob("/dev/video*"):
        match = re.fullmatch(r"/dev/video(\d+)", device_path)
        if match:
            indices.append(int(match.group(1)))
    return sorted(set(indices))


def check_camera(index: int) -> CameraCheckResult:
    """지정한 번호를 V4L2로 열어 실제 사용 가능 여부를 확인한다."""
    device_path = f"/dev/video{index}"
    capture = cv2.VideoCapture(index, cv2.CAP_V4L2)
    try:
        if not capture.isOpened():
            return CameraCheckResult(
                index=index,
                device_path=device_path,
                available=False,
                error="장치를 열 수 없습니다.",
            )

        success, frame = capture.read()
        if not success or frame is None:
            return CameraCheckResult(
                index=index,
                device_path=device_path,
                available=False,
                error="장치는 열렸지만 프레임을 읽을 수 없습니다.",
            )

        try:
            backend = capture.getBackendName()
        except (AttributeError, cv2.error):
            backend = "unknown"

        return CameraCheckResult(
            index=index,
            device_path=device_path,
            available=True,
            width=int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            height=int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
            fps=float(capture.get(cv2.CAP_PROP_FPS)),
            backend=backend,
        )
    finally:
        capture.release()


def check_connected_cameras() -> List[CameraCheckResult]:
    """발견된 모든 `/dev/videoN` 장치를 확인한다."""
    return [check_camera(index) for index in find_camera_indices()]


def main() -> int:
    results = check_connected_cameras()
    if not results:
        print("카메라 장치를 찾지 못했습니다: /dev/video* 없음")
        return 1

    for result in results:
        if result.available:
            print(
                f"카메라 {result.index}: 사용 가능 "
                f"({result.device_path}, {result.width}x{result.height}, "
                f"{result.fps:.1f} FPS, {result.backend})"
            )
        else:
            print(
                f"카메라 {result.index}: 사용 불가 "
                f"({result.device_path}) - {result.error}"
            )

    return 0 if any(result.available for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
