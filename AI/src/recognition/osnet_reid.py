"""Bounded selected-person OSNet gallery with TensorRT and ONNX backends."""

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

import cv2
import numpy as np


@dataclass(frozen=True)
class OSNetDescriptor:
    embedding: np.ndarray
    color: np.ndarray


class _TensorRTBackend:
    def __init__(self, path):
        try:
            import pycuda.driver as cuda
            import tensorrt as trt
        except ImportError as error:
            raise RuntimeError(f"OSNet TensorRT 실행 모듈 누락: {error}") from error
        self.cuda, self.trt = cuda, trt
        cuda.init()
        self.cuda_context = cuda.Device(0).retain_primary_context()
        self.cuda_context.push()
        try:
            logger = trt.Logger(trt.Logger.ERROR)
            with open(path, "rb") as model_file, trt.Runtime(logger) as runtime:
                self.engine = runtime.deserialize_cuda_engine(model_file.read())
            if self.engine is None:
                raise RuntimeError("OSNet TensorRT 엔진 역직렬화 실패")
            self.context = self.engine.create_execution_context()
            names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
            self.input_name = next(n for n in names if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
            self.output_name = next(n for n in names if self.engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
            self.input_shape = tuple(self.engine.get_tensor_shape(self.input_name))
            self.output_shape = tuple(self.engine.get_tensor_shape(self.output_name))
            if self.input_shape != (1, 3, 256, 128) or int(np.prod(self.output_shape)) != 512:
                raise RuntimeError(f"OSNet 엔진 입출력 형식 오류: {self.input_shape} -> {self.output_shape}")
            input_dtype = trt.nptype(self.engine.get_tensor_dtype(self.input_name))
            output_dtype = trt.nptype(self.engine.get_tensor_dtype(self.output_name))
            self.host_input = cuda.pagelocked_empty(int(np.prod(self.input_shape)), input_dtype)
            self.host_output = cuda.pagelocked_empty(int(np.prod(self.output_shape)), output_dtype)
            self.device_input = cuda.mem_alloc(self.host_input.nbytes)
            self.device_output = cuda.mem_alloc(self.host_output.nbytes)
            self.stream = cuda.Stream()
            self.context.set_tensor_address(self.input_name, int(self.device_input))
            self.context.set_tensor_address(self.output_name, int(self.device_output))
        finally:
            self.cuda_context.pop()

    def infer(self, tensor):
        self.cuda_context.push()
        try:
            np.copyto(self.host_input.reshape(self.input_shape), tensor)
            self.cuda.memcpy_htod_async(self.device_input, self.host_input, self.stream)
            if not self.context.execute_async_v3(self.stream.handle):
                raise RuntimeError("OSNet TensorRT 비동기 추론 실패")
            self.cuda.memcpy_dtoh_async(self.host_output, self.device_output, self.stream)
            self.stream.synchronize()
            return self.host_output.reshape(self.output_shape).copy()
        finally:
            self.cuda_context.pop()

    def close(self):
        if self.cuda_context is None:
            return
        self.cuda_context.push()
        try:
            self.device_input.free()
            self.device_output.free()
        finally:
            self.cuda_context.pop()
            self.cuda_context.detach()
            self.cuda_context = None


class OSNetReIdentifier:
    method = "OSNet + 상하의 색상 / BoT-SORT"

    def __init__(self, model_path, history_size=10, top_k=3, color_weight=0.2):
        path = Path(model_path)
        if not path.is_file():
            raise RuntimeError(f"OSNet 모델이 없습니다: {path}. AI/REID.md 참고")
        self._tensorrt = path.suffix == ".engine"
        if self._tensorrt:
            self.net = _TensorRTBackend(path)
            self.backend = f"TensorRT FP16 ({path.stem})"
        else:
            self.net = cv2.dnn.readNetFromONNX(str(path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.backend = f"OpenCV DNN CPU ({path.stem})"
        self.gallery = deque(maxlen=max(1, int(history_size)))
        self.top_k = max(1, int(top_k))
        self.color_weight = min(1.0, max(0.0, float(color_weight)))
        self.elapsed_ms = 0.0

    @property
    def samples(self):
        return len(self.gallery)

    def clear(self):
        self.gallery.clear()

    def extract(self, frame, detection):
        started = time.monotonic()
        try:
            h, w = frame.shape[:2]
            x, y, bw, bh = detection.box
            crop = frame[max(0, y):min(h, y+bh), max(0, x):min(w, x+bw)]
            if crop.size == 0 or min(crop.shape[:2]) < 8:
                return None
            color = self._color_descriptor(crop)
            rgb = cv2.cvtColor(cv2.resize(crop, (128, 256)), cv2.COLOR_BGR2RGB)
            tensor = rgb.astype(np.float32) / 255.0
            tensor = (tensor - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
            tensor = np.ascontiguousarray(tensor.transpose(2, 0, 1)[None])
            if self._tensorrt:
                feature = self.net.infer(tensor).reshape(-1).astype(np.float32)
            else:
                self.net.setInput(tensor)
                feature = self.net.forward().reshape(-1).astype(np.float32)
            norm = np.linalg.norm(feature)
            if feature.size != 512 or not np.isfinite(feature).all() or norm <= 0:
                raise RuntimeError("OSNet 출력은 유한한 512차원 임베딩이어야 합니다")
            return OSNetDescriptor(feature / norm, color)
        finally:
            self.elapsed_ms = (time.monotonic() - started) * 1000

    def remember(self, descriptor):
        if descriptor is not None:
            self.gallery.append(OSNetDescriptor(
                descriptor.embedding.astype(np.float32, copy=True),
                descriptor.color.astype(np.float32, copy=True),
            ))

    def similarity(self, descriptor):
        if descriptor is None or not self.gallery:
            return None
        embedding_weight = 1.0 - self.color_weight
        scores = sorted((
            embedding_weight * float(np.dot(saved.embedding, descriptor.embedding))
            + self.color_weight * float(np.dot(saved.color, descriptor.color))
            for saved in self.gallery
        ), reverse=True)
        selected = scores[:min(self.top_k, len(scores))]
        return float(np.mean(selected))

    @staticmethod
    def _color_descriptor(crop):
        """Return a cheap background-resistant upper/lower clothing descriptor."""
        height, width = crop.shape[:2]
        left, right = round(width * 0.1), round(width * 0.9)
        regions = (
            crop[round(height * 0.15):round(height * 0.55), left:right],
            crop[round(height * 0.55):round(height * 0.95), left:right],
        )
        features = []
        for region in regions:
            if region.size == 0:
                features.append(np.zeros(192, np.float32))
                continue
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            histogram = cv2.calcHist(
                [hsv], [0, 1, 2], None, [12, 4, 4],
                [0, 180, 0, 256, 0, 256],
            ).reshape(-1)
            total = float(histogram.sum())
            if total > 0:
                histogram /= total
            features.append(np.sqrt(histogram))
        color = np.concatenate(features).astype(np.float32)
        norm = float(np.linalg.norm(color))
        return color / norm if norm > 0 else color

    def close(self):
        if self._tensorrt:
            self.net.close()
