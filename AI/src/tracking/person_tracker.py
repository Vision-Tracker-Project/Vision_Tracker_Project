"""웹에서 선택한 한 사람을 ID와 옷차림 특징으로 고정 추적."""

from collections import deque
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


@dataclass(frozen=True)
class _ReIDDecision:
    score: float
    accepted: bool
    source: str
    priority: int = 1


class PersonTracker:
    def __init__(self, reidentifier, pan_initial=90, tilt_initial=90,
                 pan_range=(0, 180), tilt_range=(0, 180), filter_alpha=0.25,
                 gain=6.0, max_step_degrees=4.0,
                 pan_inverted=False, tilt_inverted=False,
                 reid_threshold=0.86, reid_margin=0.06, lost_timeout=3.0,
                 box_history_size=5, boundary_confirm_frames=3,
                 pan_confirm_frames=None, tilt_confirm_frames=None,
                 settle_seconds=0.3,
                 pan_start_margin=0.15, pan_release_margin=0.25,
                 head_box_ratio=0.10, head_start_band=(0.22, 0.42),
                 head_release_band=(0.28, 0.36),
                 reid_interval=0.5, reid_confirm_samples=2):
        self.reidentifier = reidentifier
        self._pan_min, self._pan_max = pan_range
        self._tilt_min, self._tilt_max = tilt_range
        self._pan = float(np.clip(pan_initial, *pan_range))
        self._tilt = float(np.clip(tilt_initial, *tilt_range))
        self._alpha = filter_alpha
        self._gain = gain
        self._max_step = max_step_degrees
        self._pan_sign = -1.0 if pan_inverted else 1.0
        self._tilt_sign = -1.0 if tilt_inverted else 1.0
        self._reid_threshold = reid_threshold
        self._reid_margin = reid_margin
        self._lost_timeout = lost_timeout
        self._reid_interval = max(0.0, reid_interval)
        self._reid_confirm_samples = max(1, reid_confirm_samples)
        self._next_reid = 0.0
        self._pending_id = None
        self._pending_count = 0
        self._was_lost = False
        self._box_history = deque(maxlen=max(1, int(box_history_size)))
        common_confirm = max(1, int(boundary_confirm_frames))
        self._confirm_frames = [
            max(1, int(pan_confirm_frames or common_confirm)),
            max(1, int(tilt_confirm_frames or common_confirm)),
        ]
        self._settle_seconds = max(0.0, float(settle_seconds))
        self._pan_margins = self._validate_margins(pan_start_margin, pan_release_margin)
        self._head_box_ratio = float(head_box_ratio)
        if not 0.0 <= self._head_box_ratio <= 0.5:
            raise ValueError("얼굴 추정 위치는 인물 박스 높이의 0~0.5 범위여야 합니다.")
        self._head_bands = self._validate_head_bands(head_start_band, head_release_band)
        self._axis_motion = [0, 0]
        self._axis_candidate = [0, 0]
        self._axis_candidate_count = [0, 0]
        self._axis_settle_until = [0.0, 0.0]
        self._filtered_center = None
        self._selected_id = None
        self._last_seen = None
        self._latest = []
        self._lock = threading.RLock()
        self.state = "선택 대기"
        self.best_candidate_id = None
        self.best_similarity = None
        self.best_reid_source = None

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
            self._reset_motion(target.box)
            self._last_seen = time.monotonic()
            self.reidentifier.clear()
            self._next_reid = 0.0
            self._pending_id = None
            self._pending_count = 0
            self._was_lost = False
            self.state = "추적 중"
            return target.track_id

    def clear_selection(self):
        with self._lock:
            self._selected_id = None
            self._reset_motion()
            self._last_seen = None
            self.reidentifier.clear()
            self._next_reid = 0.0
            self._pending_id = None
            self._pending_count = 0
            self._was_lost = False
            self.state = "선택 대기"
            self.best_candidate_id = None
            self.best_similarity = None
            self.best_reid_source = None

    def reset_target(self):
        self._reset_motion()

    def update(self, detections, frame, frame_size, move_servos=True,
               control_step_due=True):
        now = time.monotonic()
        with self._lock:
            self._latest = [(person, frame_size) for person in detections]
            for person in detections:
                person.reid_similarity = None

            if self._selected_id is None:
                self.state = "선택 대기"
                return None

            target = next((item for item in detections if item.track_id == self._selected_id), None)
            if self._last_seen is not None and now - self._last_seen > self._lost_timeout:
                self.clear_selection()
                self.state = "재식별 시간 만료 · 다시 선택하세요"
                return None
            descriptors = {}
            if target is None and not self._was_lost:
                self._next_reid = 0.0
                self._was_lost = True
            comparison_due = now >= self._next_reid
            if hasattr(self.reidentifier, "prepare"):
                self.reidentifier.prepare(
                    frame, detections, self._selected_id, now=now, force=comparison_due
                )
            matches = {}
            if comparison_due:
                candidates = [target] if target is not None else detections
                descriptors = {p.track_id: self.reidentifier.extract(frame, p)
                               for p in candidates if p.track_id >= 0}
                self._next_reid = now + self._reid_interval
                for person in candidates:
                    decision = self._match_descriptor(descriptors.get(person.track_id))
                    matches[person.track_id] = decision
                    person.reid_similarity = None if decision is None else decision.score
            tracking_state = "추적 중"
            if target is None:
                ranked = sorted(
                    ((decision.priority, decision.score, item, decision)
                     for item in detections
                     if (decision := matches.get(item.track_id)) is not None
                     and decision.accepted),
                    key=lambda candidate: (candidate[0], candidate[1]), reverse=True,
                )
                self.best_similarity = ranked[0][1] if ranked else None
                self.best_candidate_id = ranked[0][2].track_id if ranked else None
                self.best_reid_source = ranked[0][3].source if ranked else None
                second = next(
                    (candidate[1] for candidate in ranked[1:]
                     if candidate[0] == ranked[0][0]), 0.0
                ) if ranked else 0.0
                within_timeout = self._last_seen is not None and now - self._last_seen <= self._lost_timeout
                if (within_timeout and ranked
                        and ranked[0][1] - second >= self._reid_margin):
                    candidate_id = ranked[0][2].track_id
                    self._pending_count = self._pending_count + 1 if self._pending_id == candidate_id else 1
                    self._pending_id = candidate_id
                    if self._pending_count < self._reid_confirm_samples:
                        self.state = "재식별 확인 중"
                        self._reset_motion()
                        return None
                    target = ranked[0][2]
                    self._selected_id = target.track_id
                    tracking_state = f"{ranked[0][3].source} ReID 재연결"
                    self._reset_motion(target.box)
                else:
                    if comparison_due:
                        self._pending_id = None
                        self._pending_count = 0
                    self.state = "대상 유실"
                    self._reset_motion()
                    return None

            descriptor = descriptors.get(target.track_id)
            decision = matches.get(target.track_id) or self._match_descriptor(descriptor)
            similarity = None if decision is None else decision.score
            self.reidentifier.remember(descriptor)
            self._was_lost = False
            self._pending_id = None
            self._pending_count = 0
            target.reid_similarity = similarity
            self._last_seen = now
            self.best_candidate_id = target.track_id
            self.best_similarity = similarity
            self.best_reid_source = None if decision is None else decision.source
            self.state = tracking_state

            self._box_history.append(tuple(target.box))
            x, y, width, height = np.median(
                np.asarray(self._box_history, dtype=np.float32), axis=0
            )
            estimated_head_y = float(y + height * self._head_box_ratio)
            measured = (float(x + width / 2.0), estimated_head_y)
            aim_source = "박스 추정 얼굴"
            aim_low, aim_high = float(x), float(x + width)
            if hasattr(self.reidentifier, "face_box_for"):
                face_box = self.reidentifier.face_box_for(target, now=now)
                if face_box is not None:
                    face_x, face_y, face_width, face_height = face_box
                    measured = (face_x + face_width / 2, face_y + face_height / 2)
                    estimated_head_y = measured[1]
                    aim_low, aim_high = face_x, face_x + face_width
                    aim_source = "YuNet 실제 얼굴"
            if self._filtered_center is None:
                filtered = measured
            else:
                filtered = (
                    self._alpha * measured[0] + (1-self._alpha) * self._filtered_center[0],
                    self._alpha * measured[1] + (1-self._alpha) * self._filtered_center[1],
                )
            self._filtered_center = filtered
            frame_width, frame_height = frame_size
            if move_servos:
                error_x = self._boundary_error(
                    0, aim_low, aim_high, frame_width, self._pan_margins, now
                )
                error_y = self._boundary_error(
                    1, estimated_head_y, estimated_head_y, frame_height,
                    self._head_bands, now, absolute_bands=True
                )
            else:
                self._axis_motion[:] = [0, 0]
                self._axis_candidate[:] = [0, 0]
                self._axis_candidate_count[:] = [0, 0]
                self._axis_settle_until[:] = [0.0, 0.0]
                error_x = error_y = 0.0
            previous = self.angles
            if move_servos and control_step_due:
                self._pan = self._next_angle(self._pan, error_x, self._pan_sign, self._pan_min, self._pan_max)
                self._tilt = self._next_angle(self._tilt, error_y, self._tilt_sign, self._tilt_min, self._tilt_max)
            return PersonTrackingResult(filtered, *self.angles, self.angles != previous,
                                        target, aim_source, tracking_state, similarity)

    def _match_descriptor(self, descriptor):
        if descriptor is None:
            return None
        if hasattr(self.reidentifier, "match"):
            return self.reidentifier.match(
                descriptor, body_threshold=self._reid_threshold
            )
        score = self.reidentifier.similarity(descriptor)
        if score is None:
            return None
        return _ReIDDecision(score, score >= self._reid_threshold, "전신")

    def _next_angle(self, angle, error, direction, minimum, maximum):
        if error == 0.0:
            return angle
        step = float(np.clip(error*self._gain, -self._max_step, self._max_step))
        if 0.0 < abs(step) < 1.0:
            step = float(np.copysign(1.0, step))
        return float(np.clip(angle + direction*step, minimum, maximum))

    @staticmethod
    def _validate_margins(start, release):
        start, release = float(start), float(release)
        if not 0.0 <= start < release < 0.5:
            raise ValueError("안전 영역 경계는 0 <= 시작 < 복귀 < 0.5여야 합니다.")
        return start, release

    @staticmethod
    def _validate_head_bands(start_band, release_band):
        start_top, start_bottom = map(float, start_band)
        release_top, release_bottom = map(float, release_band)
        if not (0.0 <= start_top < release_top <= release_bottom
                < start_bottom <= 1.0):
            raise ValueError("얼굴 제어 경계는 시작 구간 안에 복귀 구간이 있어야 합니다.")
        return start_top, start_bottom, release_top, release_bottom

    def _reset_motion(self, initial_box=None):
        self._filtered_center = None
        self._box_history.clear()
        if initial_box is not None:
            self._box_history.append(tuple(initial_box))
        self._axis_motion[:] = [0, 0]
        self._axis_candidate[:] = [0, 0]
        self._axis_candidate_count[:] = [0, 0]
        self._axis_settle_until[:] = [0.0, 0.0]

    def _boundary_error(self, axis, low, high, extent, margins, now,
                        absolute_bands=False):
        if absolute_bands:
            start_top, start_bottom, release_top, release_bottom = margins
            start_low = extent * start_top
            start_high = extent * start_bottom
            release_low = extent * release_top
            release_high = extent * release_bottom
        else:
            start_margin, release_margin = margins
            start_low = extent * start_margin
            start_high = extent * (1.0 - start_margin)
            release_low = extent * release_margin
            release_high = extent * (1.0 - release_margin)

        crosses_low = low < start_low
        crosses_high = high > start_high
        if crosses_low and crosses_high:
            if self._axis_motion[axis] != 0:
                self._axis_settle_until[axis] = now + self._settle_seconds
            self._axis_motion[axis] = 0
            self._axis_candidate[axis] = 0
            self._axis_candidate_count[axis] = 0
            return 0.0

        motion = self._axis_motion[axis]
        if motion < 0 and low >= release_low:
            motion = 0
            self._axis_settle_until[axis] = now + self._settle_seconds
        elif motion > 0 and high <= release_high:
            motion = 0
            self._axis_settle_until[axis] = now + self._settle_seconds
        self._axis_motion[axis] = motion

        if motion == 0:
            if now < self._axis_settle_until[axis]:
                self._axis_candidate[axis] = 0
                self._axis_candidate_count[axis] = 0
                return 0.0
            candidate = -1 if crosses_low else 1 if crosses_high else 0
            if candidate == 0:
                self._axis_candidate[axis] = 0
                self._axis_candidate_count[axis] = 0
                return 0.0
            if candidate == self._axis_candidate[axis]:
                self._axis_candidate_count[axis] += 1
            else:
                self._axis_candidate[axis] = candidate
                self._axis_candidate_count[axis] = 1
            if self._axis_candidate_count[axis] < self._confirm_frames[axis]:
                return 0.0
            motion = candidate
            self._axis_motion[axis] = motion
            self._axis_candidate[axis] = 0
            self._axis_candidate_count[axis] = 0

        half_extent = max(extent / 2.0, 1.0)
        if motion < 0:
            return min(0.0, (low - release_low) / half_extent)
        return max(0.0, (high - release_high) / half_extent)

    def draw(self, frame, result):
        if hasattr(self.reidentifier, "draw"):
            self.reidentifier.draw(frame)
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
                "reid_backend": getattr(self.reidentifier, "backend", None),
                "reid_profile_samples": self.reidentifier.samples,
                "reid_similarity": self.best_similarity,
                "reid_candidate_id": self.best_candidate_id,
                "reid_source": self.best_reid_source,
                "face_reid_profile_samples": getattr(self.reidentifier, "face_samples", 0),
                "reid_threshold": self._reid_threshold,
                "reid_ms": self.reidentifier.elapsed_ms,
            }

    def close(self):
        if hasattr(self.reidentifier, "close"):
            self.reidentifier.close()
