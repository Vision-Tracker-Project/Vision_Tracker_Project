import unittest
from types import SimpleNamespace

import numpy as np

from src.detection.person_detector import PersonDetector, _nms


class _EmptyModel:
    def __init__(self):
        self.options = None

    def track(self, **options):
        self.options = options
        return [SimpleNamespace(boxes=None)]


class PersonDetectorTest(unittest.TestCase):
    def test_pytorch_fallback_requests_only_coco_person_class(self):
        detector = PersonDetector.__new__(PersonDetector)
        detector._tensorrt = False
        detector.model = _EmptyModel()
        detector.tracker = 'bytetrack.yaml'
        detector.confidence = 0.35
        detector.image_size = 640
        detector.device = 'cpu'

        self.assertEqual(detector.detect(np.zeros((32, 32, 3), np.uint8)), [])
        self.assertEqual(detector.model.options['classes'], [0])

    def test_nms_removes_lower_confidence_overlapping_box(self):
        boxes = np.array([[0, 0, 100, 100], [5, 5, 95, 95], [120, 0, 180, 80]], np.float32)
        scores = np.array([0.9, 0.7, 0.8], np.float32)
        self.assertEqual(_nms(boxes, scores), [0, 2])


if __name__ == '__main__':
    unittest.main()
