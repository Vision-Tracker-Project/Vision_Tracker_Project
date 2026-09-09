import unittest

import numpy as np

from src.detection.person_detector import PersonDetection
from src.recognition.appearance_reid import AppearanceReIdentifier
from src.tracking.person_tracker import PersonTracker


def person(track_id, box=(10, 10, 40, 80)):
    return PersonDetection(track_id, box, 0.9)


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
        self.assertEqual(result.aim_source, '박스 추정 얼굴')

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

    def test_box_jitter_inside_safe_area_does_not_move_servos(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            boundary_confirm_frames=3,
        )
        centered = person(3, (50, 20, 60, 80))
        tracker.update([centered], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        for box in ((48, 21, 62, 79), (52, 19, 58, 82), (49, 20, 61, 80)):
            tracker.update([person(3, box)], self.frame, (160, 120), move_servos=True)
        self.assertEqual(tracker.angles, (90, 90))

    def test_boundary_requires_three_consecutive_frames_before_motion(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            pan_inverted=False, boundary_confirm_frames=3, box_history_size=1,
        )
        centered = person(3, (50, 20, 60, 80))
        tracker.update([centered], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        left = person(3, (0, 20, 40, 80))
        tracker.update([left], self.frame, (160, 120), move_servos=True)
        tracker.update([left], self.frame, (160, 120), move_servos=True)
        self.assertEqual(tracker.angles, (90, 90))
        tracker.update([left], self.frame, (160, 120), move_servos=True)
        self.assertLess(tracker.angles[0], 90)

    def test_oversized_box_crossing_both_edges_does_not_chase(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            boundary_confirm_frames=1, box_history_size=1,
        )
        large = person(3, (0, 20, 160, 80))
        tracker.update([large], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        tracker.update([large], self.frame, (160, 120), move_servos=True)
        self.assertEqual(tracker.angles, (90, 90))

    def test_angle_changes_only_when_control_step_is_due(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            pan_inverted=False, boundary_confirm_frames=1, box_history_size=1,
        )
        centered = person(3, (50, 20, 60, 80))
        tracker.update([centered], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        left = person(3, (0, 20, 40, 80))
        tracker.update(
            [left], self.frame, (160, 120), move_servos=True,
            control_step_due=False,
        )
        self.assertEqual(tracker.angles, (90, 90))
        tracker.update(
            [left], self.frame, (160, 120), move_servos=True,
            control_step_due=True,
        )
        self.assertLess(tracker.angles[0], 90)

    def test_tilt_uses_estimated_head_instead_of_full_body_center(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            tilt_inverted=False, boundary_confirm_frames=1, box_history_size=1,
            head_box_ratio=0.10,
        )
        full_body = person(3, (50, 0, 60, 120))
        tracker.update([full_body], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        result = tracker.update([full_body], self.frame, (160, 120), move_servos=True)
        self.assertEqual(result.aim_source, '박스 추정 얼굴')
        self.assertAlmostEqual(result.center[1], 12.0)
        self.assertLess(tracker.angles[1], 90)

    def test_pan_can_confirm_faster_than_tilt(self):
        tracker = PersonTracker(
            AppearanceReIdentifier(), pan_initial=90, tilt_initial=90,
            pan_inverted=False, boundary_confirm_frames=3,
            pan_confirm_frames=2, tilt_confirm_frames=3, box_history_size=1,
        )
        centered = person(3, (50, 30, 60, 70))
        tracker.update([centered], self.frame, (160, 120), move_servos=True)
        tracker.select_at(0.5, 0.5)
        left_and_low_head = person(3, (0, 70, 40, 50))
        tracker.update([left_and_low_head], self.frame, (160, 120), move_servos=True)
        self.assertEqual(tracker.angles, (90, 90))
        tracker.update([left_and_low_head], self.frame, (160, 120), move_servos=True)
        self.assertLess(tracker.angles[0], 90)
        self.assertEqual(tracker.angles[1], 90)


if __name__ == '__main__':
    unittest.main()
