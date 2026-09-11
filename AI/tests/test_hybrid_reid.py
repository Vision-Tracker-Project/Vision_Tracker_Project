import unittest
from types import SimpleNamespace

import numpy as np

from src.detection.person_detector import PersonDetection
from src.detection.yunet_detector import FaceDetection
from src.recognition.hybrid_reid import HybridReIdentifier
from src.tracking.person_tracker import PersonTracker


def face(x=15, y=10, size=30):
    raw = np.array([
        x, y, size, size,
        x+8, y+10, x+22, y+10, x+15, y+16,
        x+10, y+23, x+20, y+23, 0.95,
    ], np.float32)
    return FaceDetection((x, y, size, size),
                         tuple((round(raw[i]), round(raw[i+1])) for i in range(4, 14, 2)),
                         0.95, raw)


class FakeBodyReID:
    backend = "fake body"

    def __init__(self):
        self.gallery = []
        self.elapsed_ms = 0.0
        self.extract_count = 0

    @property
    def samples(self):
        return len(self.gallery)

    def clear(self):
        self.gallery.clear()

    def extract(self, frame, detection):
        self.extract_count += 1
        result = np.zeros(4, np.float32)
        result[detection.track_id % 4] = 1
        return result

    def remember(self, descriptor):
        if descriptor is not None:
            self.gallery.append(descriptor)

    def similarity(self, descriptor):
        if descriptor is None or not self.gallery:
            return None
        return max(float(np.dot(x, descriptor)) for x in self.gallery)


class FakeFaceDetector:
    def __init__(self, detections):
        self.detections = detections
        self.shapes = []

    def detect(self, frame):
        self.shapes.append(frame.shape[:2])
        return list(self.detections)


class FakeFaceExtractor:
    def __init__(self, vector):
        self.vector = np.asarray(vector, np.float32)

    def extract(self, frame, detection):
        return SimpleNamespace(vector=self.vector)


class HybridReIDTest(unittest.TestCase):
    def make_hybrid(self, faces=(None,), vector=(1, 0, 0, 0)):
        detections = [] if faces == (None,) else list(faces)
        return HybridReIdentifier(
            FakeBodyReID(), FakeFaceDetector(detections), FakeFaceExtractor(vector),
            minimum_face_size=20, face_interval=0,
        )

    def test_selected_person_uses_upper_body_roi_and_real_face_aim(self):
        hybrid = self.make_hybrid((face(),))
        person = PersonDetection(1, (10, 5, 80, 150), 0.9)
        frame = np.zeros((240, 320, 3), np.uint8)
        hybrid.prepare(frame, [person], selected_id=1, now=10)
        self.assertEqual(hybrid.face_detector.shapes[-1], (90, 96))
        self.assertIsNotNone(hybrid.face_box_for(person, now=10))

        tracker = PersonTracker(hybrid, reid_interval=0, boundary_confirm_frames=1)
        tracker.update([person], frame, (320, 240), move_servos=False)
        tracker.select_at(0.1, 0.2)
        result = tracker.update([person], frame, (320, 240), move_servos=False)
        self.assertEqual(result.aim_source, "YuNet 실제 얼굴")

    def test_face_match_has_priority_over_body_match(self):
        hybrid = self.make_hybrid((face(),), vector=(1, 0, 0, 0))
        person = PersonDetection(1, (0, 0, 80, 150), 0.9)
        frame = np.zeros((200, 160, 3), np.uint8)
        hybrid.prepare(frame, [person], 1, now=1)
        descriptor = hybrid.extract(frame, person)
        hybrid.remember(descriptor)
        match = hybrid.match(descriptor)
        self.assertTrue(match.accepted)
        self.assertEqual((match.source, match.priority), ("얼굴", 2))

    def test_body_fallback_when_face_is_unavailable(self):
        hybrid = self.make_hybrid()
        person = PersonDetection(2, (0, 0, 80, 150), 0.9)
        frame = np.zeros((200, 160, 3), np.uint8)
        descriptor = hybrid.extract(frame, person)
        hybrid.remember(descriptor)
        match = hybrid.match(descriptor, body_threshold=0.8)
        self.assertTrue(match.accepted)
        self.assertEqual((match.source, match.priority), ("전신", 1))

    def test_face_mismatch_does_not_fall_back_to_matching_clothes(self):
        hybrid = self.make_hybrid((face(),), vector=(1, 0, 0, 0))
        person = PersonDetection(1, (0, 0, 80, 150), 0.9)
        frame = np.zeros((200, 160, 3), np.uint8)
        hybrid.prepare(frame, [person], 1, now=1)
        enrolled = hybrid.extract(frame, person)
        hybrid.remember(enrolled)
        hybrid.face_extractor.vector = np.array((0, 1, 0, 0), np.float32)
        hybrid.prepare(frame, [person], 1, now=2)
        candidate = hybrid.extract(frame, person)
        match = hybrid.match(candidate, body_threshold=0.8)
        self.assertFalse(match.accepted)
        self.assertEqual(match.source, "얼굴")

    def test_lost_face_candidate_skips_redundant_body_inference(self):
        hybrid = self.make_hybrid((face(),), vector=(1, 0, 0, 0))
        enrolled_person = PersonDetection(1, (0, 0, 80, 150), 0.9)
        frame = np.zeros((200, 160, 3), np.uint8)
        hybrid.prepare(frame, [enrolled_person], 1, now=1)
        hybrid.remember(hybrid.extract(frame, enrolled_person))
        before = hybrid.body.extract_count
        returning_person = PersonDetection(9, (0, 0, 80, 150), 0.9)
        hybrid.prepare(frame, [returning_person], selected_id=1, now=2)
        descriptor = hybrid.extract(frame, returning_person)
        self.assertIsNone(descriptor.body)
        self.assertEqual(hybrid.body.extract_count, before)

    def test_lost_target_scans_full_frame(self):
        hybrid = self.make_hybrid((face(),))
        frame = np.zeros((240, 320, 3), np.uint8)
        candidate = PersonDetection(7, (0, 0, 80, 150), 0.9)
        hybrid.prepare(frame, [candidate], selected_id=99, now=1)
        self.assertEqual(hybrid.face_detector.shapes[-1], (240, 320))
