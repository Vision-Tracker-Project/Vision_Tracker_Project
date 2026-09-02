"""PyQt에 의존하지 않는 OpenCV USB 카메라 래퍼."""

from dataclasses import dataclass
import sys
from typing import Optional

import cv2
import numpy as np


class CameraError(RuntimeError):
    """카메라 오류의 기본 예외."""


class CameraOpenError(CameraError):
    """카메라 장치를 열지 못했을 때 발생한다."""


class FrameReadError(CameraError):
    """카메라 프레임을 읽지 못했을 때 발생한다."""


@dataclass(frozen=True)
class CameraInfo:
    """드라이버에 실제 적용된 캡처 설정."""

    width: int
    height: int
    fps: float
    backend: str


class CameraCapture:
    """OpenCV VideoCapture의 생성, 읽기, 해제를 담당한다."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self._capture: Optional[cv2.VideoCapture] = None

    @property
    def is_opened(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> CameraInfo:
        """카메라를 열고 실제 적용된 설정을 반환한다."""
        if self.is_opened:
            return self.get_info()

        self.release()
        backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.camera_index, backend)

        # 드라이버에 따라 명시적 V4L2 열기가 실패할 수 있어 기본 백엔드로 재시도한다.
        if not capture.isOpened() and backend == cv2.CAP_V4L2:
            capture.release()
            capture = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)

        if not capture.isOpened():
            capture.release()
            raise CameraOpenError(
                f"카메라 {self.camera_index}을(를) 열 수 없습니다. "
                "장치 번호, 연결 상태 및 /dev/video* 권한을 확인하세요."
            )

        self._capture = capture
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        return self.get_info()

    def read(self) -> np.ndarray:
        """프레임 한 장을 반환하고 실패하면 명확한 예외를 발생시킨다."""
        if not self.is_opened:
            raise FrameReadError("카메라가 열려 있지 않습니다. open()을 먼저 호출하세요.")

        success, frame = self._capture.read()
        if not success or frame is None or frame.size == 0:
            raise FrameReadError(f"카메라 {self.camera_index}에서 프레임을 읽지 못했습니다.")
        return frame

    def get_info(self) -> CameraInfo:
        """실제 해상도, FPS 및 백엔드 이름을 반환한다."""
        if not self.is_opened:
            raise CameraOpenError("카메라 정보 조회 전에 카메라를 열어야 합니다.")

        try:
            backend_name = self._capture.getBackendName()
        except (AttributeError, cv2.error):
            backend_name = "unknown"

        return CameraInfo(
            width=int(round(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            height=int(round(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
            fps=float(self._capture.get(cv2.CAP_PROP_FPS)),
            backend=backend_name,
        )

    def release(self) -> None:
        """카메라를 안전하게 해제한다. 반복 호출해도 안전하다."""
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()

    def __enter__(self) -> "CameraCapture":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
