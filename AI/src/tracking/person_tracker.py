"""웹에서 선택한 한 사람을 ID와 옷차림 특징으로 고정 추적."""

from dataclasses import dataclass
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class PersonTrackingResult:
    center: Tuple[float, float]
    pan_angle: int
    tilt_angle: int
    angles_changed: bool
    target: object
    aim_source: str
    state: str
    similarity: Optional[float]


class PersonTracker:
    def __init__(self, reidentifier, pan_initial=90, tilt_initial=90,
                 pan_range=(0, 180), tilt_range=(0, 180), filter_alpha=0.25,
                 dead_zone_ratio=0.08, gain=6.0, max_step_degrees=4.0,
                 pan_inverted=False, tilt_inverted=False,
                 reid_threshold=0.86, reid_margin=0.06, lost_timeout=3.0):
        self.reidentifier = reidentifier
        self._pan_min, self._pan_max = pan_range
        self._tilt_min, self._tilt_max = tilt_range
        self._pan = float(np.clip(pan_initial, *pan_range))
        self._tilt = float(np.clip(tilt_initial, *tilt_range))
        self._alpha = filter_alpha
        self._dead_zone = dead_zone_ratio
        self._gain = gain
        self._max_step = max_step_degrees
        self._pan_sign = -1.0 if pan_inverted else 1.0
        self._tilt_sign = -1.0 if tilt_inverted else 1.0
        self._reid_threshold = reid_threshold
        self._reid_margin = reid_margin
        self._lost_timeout = lost_timeout
        self._filtered_center = None
        self._selected_id = None
        self._last_seen = None
        self._latest = []
        self._lock = threading.RLock()
        self.state = "선택 대기"
        self.best_candidate_id = None
        self.best_similarity = None

    @property
    def selected_id(self):
        with self._lock:
            return self._selected_id

    @property
    def angles(self):
        return round(self._pan), round(self._tilt)

    def select_at(self, x_ratio, y_ratio):
        with self._lock:
            if not 0 <= x_ratio <= 1 or not 0 <= y_ratio <= 1:
                raise ValueError("대상 좌표는 0~1 범위여야 합니다.")
            containing = []
            for person, frame_size in self._latest:
                frame_width, frame_height = frame_size
                px, py = x_ratio * frame_width, y_ratio * frame_height
                x, y, width, height = person.box
                if x <= px <= x + width and y <= py <= y + height:
                    containing.append(person)
            if not containing:
                self.clear_selection()
                return None
            target = min(containing, key=lambda item: item.box[2] * item.box[3])
            self._selected_id = target.track_id
            self._filtered_center = None
            self._last_seen = time.monotonic()
            self.reidentifier.clear()
            self.state = "추적 중"
            return target.track_id

    def clear_selection(self):
        with self._lock:
            self._selected_id = None
            self._filtered_center = None
            self._last_seen = None
            self.reidentifier.clear()
            self.state = "선택 대기"
            self.best_candidate_id = None
            self.best_similarity = None

    def reset_target(self):
        self._filtered_center = None

    def update(self, detections, frame, frame_size, move_servos=True):
        now = time.monotonic()
        with self._lock:
            self._latest = [(person, frame_size) for person in detections]
            descriptors = {person.track_id: self.reidentifier.extract(frame, person)
                           for person in detections if person.track_id >= 0}
            for person in detections:
                person.reid_similarity = self.reidentifier.similarity(descriptors.get(person.track_id))

            if self._selected_id is None:
                self.state = "선택 대기"
                return None

            target = next((item for item in detections if item.track_id == self._selected_id), None)
            tracking_state = "추적 중"
            if target is None:
                ranked = sorted(
                    ((item.reid_similarity, item) for item in detections
                     if item.reid_similarity is not None),
                    key=lambda pair: pair[0], reverse=True,
                )
                self.best_similarity = ranked[0][0] if ranked else None
                self.best_candidate_id = ranked[0][1].track_id if ranked else None
                second = ranked[1][0] if len(ranked) > 1 else 0.0
                within_timeout = self._last_seen is not None and now - self._last_seen <= self._lost_timeout
                if (within_timeout and ranked and ranked[0][0] >= self._reid_threshold
                        and ranked[0][0] - second >= self._reid_margin):
                    target = ranked[0][1]
                    self._selected_id = target.track_id
                    tracking_state = "ReID 재연결"
                    self._filtered_center = None
                else:
                    self.state = "대상 유실"
                    self._filtered_center = None
                    return None

            descriptor = descriptors.get(target.track_id)
            similarity = self.reidentifier.similarity(descriptor)
            self.reidentifier.remember(descriptor)
            target.reid_similarity = similarity
            self._last_seen = now
            self.best_candidate_id = target.track_id
            self.best_similarity = similarity
            self.state = tracking_state

            measured, aim_source = target.aim_point()
            if self._filtered_center is None:
                filtered = measured
            else:
                filtered = (
                    self._alpha * measured[0] + (1-self._alpha) * self._filtered_center[0],
                    self._alpha * measured[1] + (1-self._alpha) * self._filtered_center[1],
                )
            self._filtered_center = filtered
            frame_width, frame_height = frame_size
            error_x = (filtered[0] - frame_width/2) / (frame_width/2)
            error_y = (filtered[1] - frame_height/2) / (frame_height/2)
            previous = self.angles
            if move_servos:
                self._pan = self._next_angle(self._pan, error_x, self._pan_sign, self._pan_min, self._pan_max)
                self._tilt = self._next_angle(self._tilt, error_y, self._tilt_sign, self._tilt_min, self._tilt_max)
            return PersonTrackingResult(filtered, *self.angles, self.angles != previous,
                                        target, aim_source, tracking_state, similarity)

    def _next_angle(self, angle, error, direction, minimum, maximum):
        if abs(error) <= self._dead_zone:
            return angle
        step = float(np.clip(error*self._gain, -self._max_step, self._max_step))
        return float(np.clip(angle + direction*step, minimum, maximum))

    @staticmethod
    def draw(frame, result):
        if result is not None:
            cv2.drawMarker(frame, tuple(round(v) for v in result.center), (0, 0, 255),
                           cv2.MARKER_CROSS, 20, 2, cv2.LINE_AA)
        return frame

    def status(self):
        with self._lock:
            return {
                "selected_id": self._selected_id,
                "state": self.state,
                "reid_method": self.reidentifier.method,
                "reid_profile_samples": self.reidentifier.samples,
                "reid_similarity": self.best_similarity,
                "reid_candidate_id": self.best_candidate_id,
                "reid_threshold": self._reid_threshold,
                "reid_ms": self.reidentifier.elapsed_ms,
            }
