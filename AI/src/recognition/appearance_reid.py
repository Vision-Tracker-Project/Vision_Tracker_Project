"""옷차림 색상 특징을 이용한 저비용 단일 카메라 ReID."""

from collections import deque
import time

import cv2
import numpy as np


class AppearanceReIdentifier:
    """상의·하의 HSV 히스토그램 갤러리를 저장하고 비교한다."""

    method = "상의·하의 HSV 192D"

    def __init__(self, history_size=20):
        self.gallery = deque(maxlen=history_size)
        self.elapsed_ms = 0.0

    def clear(self):
        self.gallery.clear()

    @property
    def samples(self):
        return len(self.gallery)

    @staticmethod
    def _region_histogram(region):
        if region.size == 0:
            return np.zeros(96, dtype=np.float32)
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256]).reshape(-1)
        norm = float(np.linalg.norm(histogram))
        return histogram.astype(np.float32) / norm if norm > 0 else histogram.astype(np.float32)

    def extract(self, frame, detection):
        started = time.monotonic()
        height, width = frame.shape[:2]
        x, y, box_width, box_height = detection.box
        # 배경 혼입을 줄이기 위해 인물 박스의 좌우 15%를 제외한다.
        left = int(np.clip(x + box_width * 0.15, 0, width))
        right = int(np.clip(x + box_width * 0.85, 0, width))
        upper_top = int(np.clip(y + box_height * 0.18, 0, height))
        upper_bottom = int(np.clip(y + box_height * 0.53, 0, height))
        lower_top = int(np.clip(y + box_height * 0.52, 0, height))
        lower_bottom = int(np.clip(y + box_height * 0.92, 0, height))
        descriptor = np.concatenate((
            self._region_histogram(frame[upper_top:upper_bottom, left:right]),
            self._region_histogram(frame[lower_top:lower_bottom, left:right]),
        ))
        norm = float(np.linalg.norm(descriptor))
        if norm > 0:
            descriptor /= norm
        self.elapsed_ms = (time.monotonic() - started) * 1000.0
        return descriptor

    def remember(self, descriptor):
        if descriptor is not None and np.linalg.norm(descriptor) > 0:
            self.gallery.append(descriptor.copy())

    def similarity(self, descriptor):
        if descriptor is None or not self.gallery:
            return None
        return max(float(np.dot(saved, descriptor)) for saved in self.gallery)
