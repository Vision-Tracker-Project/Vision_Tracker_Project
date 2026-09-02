"""실시간 또는 다시보기 프레임을 PNG 파일로 저장."""

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class CaptureError(RuntimeError):
    """캡처 폴더 생성 또는 이미지 저장 오류."""


class FrameCapture:
    """현재 화면 프레임의 저장 위치와 파일명 관리."""

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = Path(output_directory).expanduser()

    def set_output_directory(self, directory: Path) -> None:
        path = Path(directory).expanduser()
        if not path.is_dir():
            raise CaptureError(f"캡처 폴더를 찾을 수 없습니다: {path}")
        self.output_directory = path

    def save(self, frame: np.ndarray, source: str) -> Path:
        if frame is None or frame.size == 0:
            raise CaptureError("캡처할 화면이 없습니다.")
        if source not in {"live", "replay"}:
            raise CaptureError(f"알 수 없는 캡처 화면 종류: {source}")

        try:
            self.output_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise CaptureError(
                f"캡처 폴더를 만들 수 없습니다: {self.output_directory}"
            ) from error

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = self.output_directory / f"capture_{timestamp}_{source}.png"
        try:
            saved = cv2.imwrite(str(output_path), frame)
        except cv2.error as error:
            raise CaptureError(f"캡처 저장 실패: {error}") from error
        if not saved:
            raise CaptureError(f"캡처 저장 실패: {output_path}")
        return output_path
