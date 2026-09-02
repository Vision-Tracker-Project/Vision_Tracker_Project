import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.detection.yunet_detector import FaceDetection
from src.recognition.sface_extractor import SFaceError, SFaceExtractor


class FakeFaceRecognizer:
    def __init__(self):
        self.received_face_data = None

    def alignCrop(self, frame, face_data):
        self.received_face_data = face_data.copy()
        return np.zeros((112, 112, 3), dtype=np.uint8)

    def feature(self, aligned_face):
        return np.ones((1, 128), dtype=np.float32)


def make_detection():
    raw = np.array(
        [
            10, 20, 100, 80,
            35, 45, 75, 45, 55, 60, 40, 80, 70, 80,
            0.95,
        ],
        dtype=np.float32,
    )
    return FaceDetection(
        box=(10, 20, 100, 80),
        landmarks=((35, 45), (75, 45), (55, 60), (40, 80), (70, 80)),
        score=0.95,
        raw=raw,
    )


class SFaceExtractorTest(unittest.TestCase):
    def test_missing_model_has_clear_error(self):
        with self.assertRaisesRegex(SFaceError, "모델 파일을 찾을 수 없습니다"):
            SFaceExtractor(Path("missing-sface-model.onnx"))

    def test_extract_returns_128d_memory_vector(self):
        fake_recognizer = FakeFaceRecognizer()
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            extractor = SFaceExtractor(
                Path(model_file.name),
                recognizer_factory=lambda *args: fake_recognizer,
            )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        embedding = extractor.extract(frame, make_detection())

        self.assertEqual(fake_recognizer.received_face_data.shape, (14,))
        self.assertEqual(embedding.vector.shape, (128,))
        self.assertEqual(embedding.dimension, 128)
        self.assertAlmostEqual(embedding.l2_norm, np.sqrt(128), places=5)
        self.assertGreaterEqual(embedding.elapsed_ms, 0.0)

    def test_invalid_feature_dimension_has_clear_error(self):
        fake_recognizer = FakeFaceRecognizer()
        fake_recognizer.feature = lambda aligned: np.ones((1, 64), dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            extractor = SFaceExtractor(
                Path(model_file.name),
                recognizer_factory=lambda *args: fake_recognizer,
            )

        with self.assertRaisesRegex(SFaceError, "특징 차원이 올바르지 않습니다"):
            extractor.extract(
                np.zeros((480, 640, 3), dtype=np.uint8), make_detection()
            )


if __name__ == "__main__":
    unittest.main()
