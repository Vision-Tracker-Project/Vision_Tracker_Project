"""OpenCV FaceRecognizerSF를 이용한 메모리 전용 얼굴 특징 추출."""

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Callable

import cv2
import numpy as np

from src.detection.yunet_detector import FaceDetection


class SFaceError(RuntimeError):
    """SFace 모델 초기화, 얼굴 정렬 또는 특징 추출 오류."""


@dataclass(frozen=True)
class FaceEmbedding:
    """얼굴 한 건에서 추출한 임시 특징 벡터와 진단 정보."""

    vector: np.ndarray = field(repr=False, compare=False)
    dimension: int
    l2_norm: float
    elapsed_ms: float


class SFaceExtractor:
    """YuNet 검출 결과를 정렬하고 128차원 특징 벡터를 추출함."""

    EXPECTED_DIMENSION = 128

    def __init__(
        self,
        model_path: Path,
        recognizer_factory: Callable = None,
    ) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise SFaceError(f"SFace 모델 파일을 찾을 수 없습니다: {self.model_path}")

        factory = recognizer_factory or cv2.FaceRecognizerSF.create
        try:
            self._recognizer = factory(str(self.model_path), "")
        except cv2.error as error:
            raise SFaceError(f"SFace 모델을 불러오지 못했습니다: {error}") from error

    def extract(
        self, frame: np.ndarray, detection: FaceDetection
    ) -> FaceEmbedding:
        """특징 벡터를 추출해 메모리로 반환하며 저장은 수행하지 않음."""
        if frame is None or frame.size == 0:
            raise SFaceError("SFace에 전달된 프레임이 비어 있습니다.")

        started_at = perf_counter()
        try:
            # alignCrop은 신뢰도를 제외한 박스와 5개 랜드마크를 사용함.
            aligned_face = self._recognizer.alignCrop(frame, detection.raw[:14])
            feature = self._recognizer.feature(aligned_face)
        except cv2.error as error:
            raise SFaceError(f"SFace 특징 추출에 실패했습니다: {error}") from error

        vector = np.asarray(feature, dtype=np.float32).reshape(-1).copy()
        if vector.size != self.EXPECTED_DIMENSION:
            raise SFaceError(
                f"SFace 특징 차원이 올바르지 않습니다: {vector.size}"
            )
        if not np.isfinite(vector).all():
            raise SFaceError("SFace 특징 벡터에 유효하지 않은 값이 포함되어 있습니다.")

        elapsed_ms = (perf_counter() - started_at) * 1000.0
        return FaceEmbedding(
            vector=vector,
            dimension=vector.size,
            l2_norm=float(np.linalg.norm(vector)),
            elapsed_ms=elapsed_ms,
        )
