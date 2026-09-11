"""Face-first selected-person ReID with an OSNet body fallback."""

from collections import deque
from dataclasses import dataclass
import time

import cv2
import numpy as np

from src.detection.yunet_detector import FaceDetection


@dataclass(frozen=True)
class HybridDescriptor:
    body: object
    face: object = None


@dataclass(frozen=True)
class HybridMatch:
    score: float
    accepted: bool
    source: str
    priority: int


class HybridReIdentifier:
    """Use SFace when a usable face exists, otherwise compare OSNet body features."""

    method = "YuNet + SFace 우선 / OSNet 전신 폴백"
    def __init__(self, body_reidentifier, face_detector, face_extractor,
                 history_size=10, face_threshold=0.45,
                 face_interval=0.2, minimum_face_size=24):
        self.body = body_reidentifier
        self.backend = f"SFace OpenCV DNN + {body_reidentifier.backend}"
        self.face_detector = face_detector
        self.face_extractor = face_extractor
        self.face_gallery = deque(maxlen=max(1, int(history_size)))
        self.face_threshold = float(face_threshold)
        self.face_interval = max(0.0, float(face_interval))
        self.minimum_face_size = max(8, int(minimum_face_size))
        self._next_face_detection = 0.0
        self._fresh_faces = {}
        self._face_positions = {}
        self._visible_faces = []
        self._selected_visible = False
        self.elapsed_ms = 0.0
        self.last_match_source = None

    @property
    def samples(self):
        return self.body.samples

    @property
    def face_samples(self):
        return len(self.face_gallery)

    def clear(self):
        self.body.clear()
        self.face_gallery.clear()
        self._fresh_faces.clear()
        self._face_positions.clear()
        self._visible_faces.clear()
        self._selected_visible = False
        self.last_match_source = None

    def prepare(self, frame, detections, selected_id, now=None, force=False):
        """Detect faces in the selected upper-body ROI, or full frame while lost."""
        self._fresh_faces = {}
        self._visible_faces = []
        if selected_id is None:
            return
        now = time.monotonic() if now is None else now
        self._face_positions = {
            track_id: value for track_id, value in self._face_positions.items()
            if now - value[4] <= 2.0
        }
        if not force and now < self._next_face_detection:
            return
        self._next_face_detection = now + self.face_interval
        selected = next((p for p in detections if p.track_id == selected_id), None)
        self._selected_visible = selected is not None
        if selected is None:
            faces = self.face_detector.detect(frame)
        else:
            faces = self._detect_selected_roi(frame, selected)
        self._visible_faces = faces
        self._associate(faces, detections, now)

    def _detect_selected_roi(self, frame, person):
        frame_height, frame_width = frame.shape[:2]
        x, y, width, height = person.box
        pad = round(width * 0.1)
        left = max(0, x - pad)
        right = min(frame_width, x + width + pad)
        top = max(0, y)
        bottom = min(frame_height, y + round(height * 0.6))
        if right - left < 8 or bottom - top < 8:
            return []
        return [self._translate(face, left, top)
                for face in self.face_detector.detect(frame[top:bottom, left:right])]

    @staticmethod
    def _translate(face, offset_x, offset_y):
        raw = face.raw.copy()
        raw[0] += offset_x
        raw[1] += offset_y
        for index in range(4, 14, 2):
            raw[index] += offset_x
            raw[index + 1] += offset_y
        x, y, width, height = face.box
        return FaceDetection(
            box=(x + offset_x, y + offset_y, width, height),
            landmarks=tuple((px + offset_x, py + offset_y) for px, py in face.landmarks),
            score=face.score,
            raw=raw,
        )

    def _associate(self, faces, detections, now):
        for face in faces:
            x, y, width, height = face.box
            if min(width, height) < self.minimum_face_size:
                continue
            center_x, center_y = x + width / 2, y + height / 2
            owners = []
            for person in detections:
                px, py, pw, ph = person.box
                if (person.track_id >= 0 and px <= center_x <= px + pw
                        and py <= center_y <= py + ph * 0.6):
                    owners.append(person)
            if not owners:
                continue
            owner = min(owners, key=lambda person: person.box[2] * person.box[3])
            self._fresh_faces[owner.track_id] = face
            px, py, pw, ph = owner.box
            self._face_positions[owner.track_id] = (
                (center_x - px) / max(pw, 1),
                (center_y - py) / max(ph, 1),
                width / max(pw, 1),
                height / max(ph, 1),
                now,
            )

    def face_box_for(self, detection, now=None, max_age=0.6):
        position = self._face_positions.get(detection.track_id)
        now = time.monotonic() if now is None else now
        if position is None or now - position[4] > max_age:
            return None
        rx, ry, rw, rh, _ = position
        x, y, width, height = detection.box
        face_width, face_height = width * rw, height * rh
        center_x, center_y = x + width * rx, y + height * ry
        return (center_x - face_width / 2, center_y - face_height / 2,
                face_width, face_height)

    def extract(self, frame, detection):
        started = time.monotonic()
        face = None
        face_detection = self._fresh_faces.get(detection.track_id)
        if face_detection is not None:
            embedding = self.face_extractor.extract(frame, face_detection)
            vector = embedding.vector.astype(np.float32, copy=True)
            norm = float(np.linalg.norm(vector))
            face = vector / norm if norm > 0 else None
        # While lost, a usable face can be decided by SFace alone. Avoid an
        # unnecessary OSNet pass for that candidate; people without faces use body ReID.
        needs_body = self._selected_visible or face is None or not self.face_gallery
        body = self.body.extract(frame, detection) if needs_body else None
        self.elapsed_ms = (time.monotonic() - started) * 1000
        return HybridDescriptor(body=body, face=face)

    def remember(self, descriptor):
        if descriptor is None:
            return
        self.body.remember(descriptor.body)
        if descriptor.face is not None:
            similarity = (max(float(np.dot(saved, descriptor.face))
                              for saved in self.face_gallery)
                          if self.face_gallery else 1.0)
            if similarity >= self.face_threshold:
                self.face_gallery.append(descriptor.face.copy())

    def match(self, descriptor, body_threshold=0.85):
        if descriptor is None:
            return None
        if descriptor.face is not None and self.face_gallery:
            score = max(float(np.dot(saved, descriptor.face)) for saved in self.face_gallery)
            self.last_match_source = "얼굴"
            return HybridMatch(score, score >= self.face_threshold, "얼굴", 2)
        score = self.body.similarity(descriptor.body)
        if score is None:
            return None
        self.last_match_source = "전신"
        return HybridMatch(score, score >= body_threshold, "전신", 1)

    def similarity(self, descriptor):
        match = self.match(descriptor)
        return None if match is None else match.score

    def draw(self, frame):
        for face in self._visible_faces:
            x, y, width, height = face.box
            cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 180, 0), 2)
            cv2.putText(frame, f"Face {face.score:.2f}", (x, max(18, y - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1, cv2.LINE_AA)
        return frame

    def close(self):
        if hasattr(self.body, "close"):
            self.body.close()
