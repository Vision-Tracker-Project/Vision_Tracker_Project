"""OpenCV FaceDetectorYN을 이용한 YuNet 얼굴 검출."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Tuple

import cv2
import numpy as np


class YuNetError(RuntimeError):
    """YuNet 모델 초기화 또는 추론 오류."""


@dataclass(frozen=True)
class FaceDetection:
    """YuNet 얼굴 한 건의 검출 결과."""

    box: Tuple[int, int, int, int]
    landmarks: Tuple[Tuple[int, int], ...]
    score: float
    raw: np.ndarray = field(repr=False, compare=False)


class YuNetDetector:
    """프레임 크기에 맞춰 OpenCV YuNet 추론을 수행한다."""

    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.8,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        detector_factory: Callable = None,
    ) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise YuNetError(f"YuNet 모델 파일을 찾을 수 없습니다: {self.model_path}")

        factory = detector_factory or cv2.FaceDetectorYN.create
        try:
            self._detector = factory(
                str(self.model_path),
                "",
                (320, 320),
                score_threshold,
                nms_threshold,
                top_k,
            )
        except cv2.error as error:
            raise YuNetError(f"YuNet 모델을 불러오지 못했습니다: {error}") from error

        self._input_size = (320, 320)

    def detect(self, frame: np.ndarray) -> List[FaceDetection]:
        """BGR 프레임에서 얼굴 박스, 랜드마크, 신뢰도를 검출한다."""
        if frame is None or frame.size == 0:
            raise YuNetError("YuNet에 전달된 프레임이 비어 있습니다.")

        height, width = frame.shape[:2]
        input_size = (width, height)
        if input_size != self._input_size:
            self._detector.setInputSize(input_size)
            self._input_size = input_size

        try:
            _, faces = self._detector.detect(frame)
        except cv2.error as error:
            raise YuNetError(f"YuNet 얼굴 검출에 실패했습니다: {error}") from error

        if faces is None:
            return []

        detections = []
        for face in faces:
            raw = np.asarray(face, dtype=np.float32).copy()
            box = tuple(int(round(value)) for value in raw[:4])
            landmarks = tuple(
                (int(round(raw[index])), int(round(raw[index + 1])))
                for index in range(4, 14, 2)
            )
            detections.append(
                FaceDetection(
                    box=box,
                    landmarks=landmarks,
                    score=float(raw[14]),
                    raw=raw,
                )
            )
        return detections

    @staticmethod
    def draw(frame: np.ndarray, detections: List[FaceDetection]) -> np.ndarray:
        """검출된 얼굴 박스, 신뢰도와 5개 랜드마크를 프레임에 그린다."""
        for detection in detections:
            x, y, width, height = detection.box
            cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"Face {detection.score:.2f}",
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            for point in detection.landmarks:
                cv2.circle(frame, point, 2, (0, 255, 255), -1, cv2.LINE_AA)
        return frame
