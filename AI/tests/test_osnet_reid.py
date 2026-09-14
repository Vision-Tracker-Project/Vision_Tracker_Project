import unittest
from unittest.mock import patch

import numpy as np

from src.detection.person_detector import PersonDetection
from src.recognition.osnet_reid import OSNetReIdentifier
from src.tracking.person_tracker import PersonTracker


class OSNetTest(unittest.TestCase):
    def make_reid(self):
        with patch('src.recognition.osnet_reid.Path.is_file', return_value=True), patch(
                'src.recognition.osnet_reid._TensorRTBackend') as load:
            load.return_value.infer.return_value = np.ones((1, 512), np.float32)
            return OSNetReIdentifier('fake.engine', history_size=10)

    def test_normalization_and_bounded_gallery(self):
        reid = self.make_reid()
        frame = np.zeros((80, 40, 3), np.uint8)
        feature = reid.extract(frame, PersonDetection(1, (0, 0, 40, 80), 0.9))
        self.assertAlmostEqual(float(np.linalg.norm(feature)), 1.0, places=5)
        blob = reid.net.infer.call_args.args[0]
        self.assertEqual(blob.shape, (1, 3, 256, 128))
        self.assertAlmostEqual(float(blob[0, 0, 0, 0]), -0.485/0.229, places=5)
        for _ in range(50):
            reid.remember(feature)
        self.assertEqual(reid.samples, 10)
        self.assertAlmostEqual(reid.similarity(feature), 1.0, places=5)

    def test_default_gallery_keeps_twenty_features(self):
        with patch('src.recognition.osnet_reid.Path.is_file', return_value=True), patch(
                'src.recognition.osnet_reid._TensorRTBackend'):
            reid = OSNetReIdentifier('fake.engine')
        feature = np.ones(512, np.float32) / np.sqrt(512)
        for _ in range(25):
            reid.remember(feature)
        self.assertEqual(reid.samples, 20)

    @patch('src.tracking.person_tracker.time.monotonic')
    def test_long_absence_confirmation_expiry_and_no_idle_inference(self, clock):
        clock.return_value = 100.0
        reid = self.make_reid()
        tracker = PersonTracker(reid, lost_timeout=60)
        frame = np.zeros((120, 80, 3), np.uint8)
        original = PersonDetection(1, (20, 20, 40, 80), 0.9)
        replacement = PersonDetection(9, (20, 20, 40, 80), 0.9)
        tracker.update([original], frame, (80, 120))
        reid.net.infer.assert_not_called()
        tracker.select_at(0.5, 0.5)
        tracker.update([original], frame, (80, 120))
        clock.return_value = 100.1
        tracker.update([original], frame, (80, 120))
        self.assertEqual(reid.net.infer.call_count, 1)
        clock.return_value = 110
        self.assertIsNone(tracker.update([replacement], frame, (80, 120)))
        clock.return_value = 110.6
        reconnected = tracker.update([replacement], frame, (80, 120))
        self.assertEqual(reconnected.target.tracker_id, 9)
        self.assertEqual(reconnected.target.track_id, 1)
        self.assertEqual(tracker.selected_id, 1)
        clock.return_value = 171
        self.assertIsNone(tracker.update([original], frame, (80, 120)))
        self.assertIsNone(tracker.selected_id)
        self.assertEqual(reid.samples, 0)

    @patch('src.tracking.person_tracker.time.monotonic', return_value=100)
    def test_ambiguous_candidates_are_not_reconnected(self, clock):
        reid = self.make_reid()
        tracker = PersonTracker(
            reid, lost_timeout=60, reid_interval=0, long_reid_delay=0
        )
        frame = np.zeros((120, 80, 3), np.uint8)
        p = lambda i: PersonDetection(i, (20, 20, 40, 80), 0.9)
        tracker.update([p(1)], frame, (80, 120))
        tracker.select_at(0.5, 0.5)
        tracker.update([p(1)], frame, (80, 120))
        for _ in range(3):
            self.assertIsNone(tracker.update([p(2), p(3)], frame, (80, 120)))
        self.assertEqual(tracker.selected_id, 1)

    def test_osnet_search_waits_for_short_term_tracker(self):
        now = [0.0]
        reid = self.make_reid()
        tracker = PersonTracker(
            reid, lost_timeout=60, reid_interval=0,
            long_reid_delay=1.0, clock=lambda: now[0],
        )
        frame = np.zeros((120, 80, 3), np.uint8)
        original = PersonDetection(1, (20, 20, 40, 80), 0.9)
        candidate = PersonDetection(9, (20, 20, 40, 80), 0.9)
        tracker.update([original], frame, (80, 120))
        tracker.select_at(0.5, 0.5)
        tracker.update([original], frame, (80, 120))
        baseline = reid.net.infer.call_count

        now[0] = 0.5
        self.assertIsNone(tracker.update([candidate], frame, (80, 120)))
        self.assertEqual(reid.net.infer.call_count, baseline)
        now[0] = 1.5
        self.assertIsNone(tracker.update([candidate], frame, (80, 120)))
        self.assertEqual(reid.net.infer.call_count, baseline + 1)
