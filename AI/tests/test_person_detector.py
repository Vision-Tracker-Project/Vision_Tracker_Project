import unittest
from unittest.mock import Mock

import numpy as np

from src.detection.person_detector import PersonDetector, _BoTSORTAppearanceEncoder, _nms


class PersonDetectorTest(unittest.TestCase):
    def test_empty_tensorrt_result_updates_tracker(self):
        detector = PersonDetector.__new__(PersonDetector)
        detector.model = Mock(input_shape=(1, 3, 32, 32))
        detector.model.infer.return_value = np.zeros((1, 5, 1), np.float32)
        detector.byte_tracker = Mock()
        detector.confidence = 0.35

        self.assertEqual(detector.detect(np.zeros((32, 32, 3), np.uint8)), [])
        detector.byte_tracker.update.assert_called_once()

    def test_nms_removes_lower_confidence_overlapping_box(self):
        boxes = np.array([[0, 0, 100, 100], [5, 5, 95, 95], [120, 0, 180, 80]], np.float32)
        scores = np.array([0.9, 0.7, 0.8], np.float32)
        self.assertEqual(_nms(boxes, scores), [0, 2])

    def test_internal_reid_encoder_distinguishes_appearance(self):
        encoder = _BoTSORTAppearanceEncoder()
        red = np.full((80, 40, 3), (0, 0, 255), np.uint8)
        blue = np.full((80, 40, 3), (255, 0, 0), np.uint8)
        box = np.array([[20, 40, 40, 80, 0]], np.float32)

        red_feature = encoder(red, box)[0]
        blue_feature = encoder(blue, box)[0]
        self.assertAlmostEqual(float(np.linalg.norm(red_feature)), 1.0, places=5)
        self.assertLess(float(np.dot(red_feature, blue_feature)), 0.5)


if __name__ == '__main__':
    unittest.main()
