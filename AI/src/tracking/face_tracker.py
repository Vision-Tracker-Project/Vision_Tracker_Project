"""검출 얼굴 중심을 필터링하고 팬·틸트 목표 각도로 변환."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.detection.yunet_detector import FaceDetection


@dataclass(frozen=True)
class TrackingResult:
    """한 프레임의 추적 대상과 계산된 목표 각도."""

    center: Tuple[float, float]
    pan_angle: int
    tilt_angle: int
    angles_changed: bool
    target: FaceDetection


class FaceTracker:
    """가장 큰 얼굴을 선택하고 누적 방식으로 팬·틸트 각도를 계산."""

    def __init__(
        self,
        pan_initial: int = 90,
        tilt_initial: int = 90,
        pan_range: Tuple[int, int] = (0, 180),
        tilt_range: Tuple[int, int] = (0, 180),
        filter_alpha: float = 0.25,
        dead_zone_ratio: float = 0.08,
        gain: float = 6.0,
        max_step_degrees: float = 4.0,
        pan_inverted: bool = False,
        tilt_inverted: bool = False,
    ) -> None:
        if not 0.0 < filter_alpha <= 1.0:
            raise ValueError("filter_alpha는 0보다 크고 1 이하여야 합니다.")
        if not 0.0 <= dead_zone_ratio < 1.0:
            raise ValueError("dead_zone_ratio는 0 이상 1 미만이어야 합니다.")
        if gain <= 0.0 or max_step_degrees <= 0.0:
            raise ValueError("gain과 max_step_degrees는 0보다 커야 합니다.")

        self._pan_min, self._pan_max = pan_range
        self._tilt_min, self._tilt_max = tilt_range
        self._pan = float(np.clip(pan_initial, self._pan_min, self._pan_max))
        self._tilt = float(np.clip(tilt_initial, self._tilt_min, self._tilt_max))
        self._alpha = filter_alpha
        self._dead_zone = dead_zone_ratio
        self._gain = gain
        self._max_step = max_step_degrees
        self._pan_sign = -1.0 if pan_inverted else 1.0
        self._tilt_sign = -1.0 if tilt_inverted else 1.0
        self._filtered_center: Optional[Tuple[float, float]] = None

    @property
    def angles(self) -> Tuple[int, int]:
        return round(self._pan), round(self._tilt)

    def reset_target(self) -> None:
        """얼굴이 사라졌을 때 이전 좌표 필터만 초기화."""
        self._filtered_center = None

    def update(
        self,
        detections: List[FaceDetection],
        frame_size: Tuple[int, int],
    ) -> Optional[TrackingResult]:
        """가장 큰 얼굴의 중심 오차로 다음 팬·틸트 각도 계산."""
        if not detections:
            self.reset_target()
            return None

        frame_width, frame_height = frame_size
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("프레임 크기는 0보다 커야 합니다.")

        target = max(detections, key=lambda item: item.box[2] * item.box[3])
        x, y, width, height = target.box
        measured = (x + width / 2.0, y + height / 2.0)
        if self._filtered_center is None:
            filtered = measured
        else:
            filtered = (
                self._alpha * measured[0]
                + (1.0 - self._alpha) * self._filtered_center[0],
                self._alpha * measured[1]
                + (1.0 - self._alpha) * self._filtered_center[1],
            )
        self._filtered_center = filtered

        error_x = (filtered[0] - frame_width / 2.0) / (frame_width / 2.0)
        error_y = (filtered[1] - frame_height / 2.0) / (frame_height / 2.0)
        previous = self.angles
        self._pan = self._next_angle(
            self._pan, error_x, self._pan_sign, self._pan_min, self._pan_max
        )
        self._tilt = self._next_angle(
            self._tilt, error_y, self._tilt_sign, self._tilt_min, self._tilt_max
        )
        current = self.angles

        return TrackingResult(
            center=filtered,
            pan_angle=current[0],
            tilt_angle=current[1],
            angles_changed=current != previous,
            target=target,
        )

    def _next_angle(
        self,
        angle: float,
        normalized_error: float,
        direction: float,
        minimum: int,
        maximum: int,
    ) -> float:
        if abs(normalized_error) <= self._dead_zone:
            return angle
        step = float(np.clip(normalized_error * self._gain, -self._max_step, self._max_step))
        return float(np.clip(angle + direction * step, minimum, maximum))

    @staticmethod
    def draw(frame: np.ndarray, result: Optional[TrackingResult]) -> np.ndarray:
        """선택된 추적 대상과 필터링 중심을 화면에 표시."""
        if result is None:
            return frame
        x, y, width, height = result.target.box
        center = (round(result.center[0]), round(result.center[1]))
        cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 128, 0), 3)
        cv2.drawMarker(
            frame,
            center,
            (0, 0, 255),
            cv2.MARKER_CROSS,
            18,
            2,
            cv2.LINE_AA,
        )
        return frame
