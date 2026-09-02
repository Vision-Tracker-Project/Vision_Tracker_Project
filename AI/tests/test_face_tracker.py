import unittest

import numpy as np

from src.detection.yunet_detector import FaceDetection
from src.tracking.face_tracker import FaceTracker


def make_detection(x, y, width, height):
    return FaceDetection(
        box=(x, y, width, height),
        landmarks=(),
        score=0.9,
        raw=np.zeros(15, dtype=np.float32),
    )


class FaceTrackerTest(unittest.TestCase):
    def test_no_face_returns_none(self):
        tracker = FaceTracker()
        self.assertIsNone(tracker.update([], (640, 480)))

    def test_largest_face_is_selected(self):
        tracker = FaceTracker(filter_alpha=1.0)
        small = make_detection(10, 10, 20, 20)
        large = make_detection(400, 200, 100, 100)

        result = tracker.update([small, large], (640, 480))

        self.assertIs(result.target, large)
        self.assertEqual(result.center, (450.0, 250.0))

    def test_center_face_keeps_initial_angles(self):
        tracker = FaceTracker(filter_alpha=1.0)
        result = tracker.update([make_detection(270, 190, 100, 100)], (640, 480))

        self.assertEqual((result.pan_angle, result.tilt_angle), (90, 90))
        self.assertFalse(result.angles_changed)

    def test_off_center_face_changes_and_clamps_angles(self):
        tracker = FaceTracker(
            pan_initial=179,
            tilt_initial=1,
            filter_alpha=1.0,
            gain=20.0,
            max_step_degrees=10.0,
            tilt_inverted=True,
        )
        result = tracker.update([make_detection(600, 400, 40, 40)], (640, 480))

        self.assertEqual(result.pan_angle, 180)
        self.assertEqual(result.tilt_angle, 0)
        self.assertTrue(result.angles_changed)


if __name__ == "__main__":
    unittest.main()
