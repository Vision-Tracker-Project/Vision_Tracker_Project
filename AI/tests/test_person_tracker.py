import unittest

import numpy as np

from src.detection.pose_detector import PersonDetection
from src.recognition.appearance_reid import AppearanceReIdentifier
from src.tracking.person_tracker import PersonTracker


def person(track_id, box=(10, 10, 40, 80)):
    points = np.zeros((17, 3), np.float32)
    points[5] = (20, 30, 0.9)
    points[6] = (40, 30, 0.9)
    return PersonDetection(track_id, box, 0.9, points)


class PersonTrackerTest(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((120, 160, 3), (30, 80, 180), np.uint8)
        self.tracker = PersonTracker(AppearanceReIdentifier(), reid_threshold=0.8)

    def test_user_selects_only_person_under_point(self):
        detections = [person(3), person(8, (90, 10, 40, 80))]
        self.tracker.update(detections, self.frame, (160, 120), move_servos=False)
        self.assertEqual(self.tracker.select_at(0.2, 0.3), 3)
        result = self.tracker.update(detections, self.frame, (160, 120), move_servos=False)
        self.assertEqual(result.target.track_id, 3)
        self.assertEqual(result.aim_source, '어깨')

    def test_larger_person_does_not_replace_selected_id(self):
        detections = [person(3), person(8, (70, 5, 80, 110))]
        self.tracker.update(detections, self.frame, (160, 120), move_servos=False)
        self.tracker.select_at(0.2, 0.3)
        result = self.tracker.update(detections, self.frame, (160, 120), move_servos=False)
        self.assertEqual(result.target.track_id, 3)

    def test_blank_point_clears_selection(self):
        detections = [person(3)]
        self.tracker.update(detections, self.frame, (160, 120), move_servos=False)
        self.tracker.select_at(0.2, 0.3)
        self.assertIsNone(self.tracker.select_at(0.9, 0.9))
        self.assertIsNone(self.tracker.selected_id)


if __name__ == '__main__':
    unittest.main()
