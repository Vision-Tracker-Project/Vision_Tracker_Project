import unittest
from unittest.mock import patch

import numpy as np

from src.detection.person_detector import PersonDetection
from src.recognition.osnet_reid import OSNetReIdentifier
from src.tracking.person_tracker import PersonTracker


class OSNetTest(unittest.TestCase):
    def make_reid(self):
        with patch('src.recognition.osnet_reid.Path.is_file', return_value=True), patch(
                'src.recognition.osnet_reid.cv2.dnn.readNetFromONNX') as load:
            load.return_value.forward.return_value = np.ones((1, 512), np.float32)
            return OSNetReIdentifier('fake.onnx', history_size=10)

    def test_normalization_and_bounded_gallery(self):
        reid = self.make_reid()
        frame = np.zeros((80, 40, 3), np.uint8)
        feature = reid.extract(frame, PersonDetection(1, (0, 0, 40, 80), 0.9))
        self.assertAlmostEqual(float(np.linalg.norm(feature)), 1.0, places=5)
        blob = reid.net.setInput.call_args.args[0]
        self.assertEqual(blob.shape, (1, 3, 256, 128))
        self.assertAlmostEqual(float(blob[0, 0, 0, 0]), -0.485/0.229, places=5)
        for _ in range(50):
            reid.remember(feature)
        self.assertEqual(reid.samples, 10)
        self.assertAlmostEqual(reid.similarity(feature), 1.0, places=5)

    @patch('src.tracking.person_tracker.time.monotonic')
    def test_long_absence_confirmation_expiry_and_no_idle_inference(self, clock):
        clock.return_value = 100.0
        reid = self.make_reid()
        tracker = PersonTracker(reid, lost_timeout=60)
        frame = np.zeros((80, 40, 3), np.uint8)
        original = PersonDetection(1, (0, 0, 40, 80), 0.9)
        replacement = PersonDetection(9, (0, 0, 40, 80), 0.9)
        tracker.update([original], frame, (40, 80))
        reid.net.forward.assert_not_called()
        tracker.select_at(0.5, 0.5)
        tracker.update([original], frame, (40, 80))
        clock.return_value = 100.1
        tracker.update([original], frame, (40, 80))
        self.assertEqual(reid.net.forward.call_count, 1)
        clock.return_value = 110
        self.assertIsNone(tracker.update([replacement], frame, (40, 80)))
        clock.return_value = 110.6
        self.assertEqual(tracker.update([replacement], frame, (40, 80)).target.track_id, 9)
        clock.return_value = 171
        self.assertIsNone(tracker.update([original], frame, (40, 80)))
        self.assertIsNone(tracker.selected_id)
        self.assertEqual(reid.samples, 0)

    @patch('src.tracking.person_tracker.time.monotonic', return_value=100)
    def test_ambiguous_candidates_are_not_reconnected(self, clock):
        reid = self.make_reid()
        tracker = PersonTracker(reid, lost_timeout=60, reid_interval=0)
        frame = np.zeros((80, 40, 3), np.uint8)
        p = lambda i: PersonDetection(i, (0, 0, 40, 80), 0.9)
        tracker.update([p(1)], frame, (40, 80))
        tracker.select_at(0.5, 0.5)
        tracker.update([p(1)], frame, (40, 80))
        for _ in range(3):
            self.assertIsNone(tracker.update([p(2), p(3)], frame, (40, 80)))
        self.assertEqual(tracker.selected_id, 1)
