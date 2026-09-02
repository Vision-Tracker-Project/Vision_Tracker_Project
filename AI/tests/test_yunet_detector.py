import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.detection.yunet_detector import YuNetDetector, YuNetError


class FakeFaceDetector:
    def __init__(self):
        self.input_size = None

    def setInputSize(self, input_size):
        self.input_size = input_size

    def detect(self, frame):
        face = np.array(
            [
                10, 20, 100, 80,
                35, 45, 75, 45, 55, 60, 40, 80, 70, 80,
                0.95,
            ],
            dtype=np.float32,
        )
        return 1, np.expand_dims(face, axis=0)


class YuNetDetectorTest(unittest.TestCase):
    def test_missing_model_has_clear_error(self):
        with self.assertRaisesRegex(YuNetError, "모델 파일을 찾을 수 없습니다"):
            YuNetDetector(Path("missing-yunet-model.onnx"))

    def test_detect_converts_opencv_output(self):
        fake_detector = FakeFaceDetector()
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            detector = YuNetDetector(
                Path(model_file.name),
                detector_factory=lambda *args: fake_detector,
            )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(frame)

        self.assertEqual(fake_detector.input_size, (640, 480))
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].box, (10, 20, 100, 80))
        self.assertEqual(len(detections[0].landmarks), 5)
        self.assertAlmostEqual(detections[0].score, 0.95, places=5)
        self.assertEqual(detections[0].raw.shape, (15,))

    def test_draw_adds_detection_overlay(self):
        fake_detector = FakeFaceDetector()
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model_file:
            detector = YuNetDetector(
                Path(model_file.name),
                detector_factory=lambda *args: fake_detector,
            )

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        detections = detector.detect(frame)
        output = detector.draw(frame, detections)

        self.assertIs(output, frame)
        self.assertGreater(np.count_nonzero(output), 0)


if __name__ == "__main__":
    unittest.main()
