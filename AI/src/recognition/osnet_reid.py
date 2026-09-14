"""TensorRT OSNet 기반 선택 인물 ReID 갤러리."""

from collections import deque
from pathlib import Path
import time

import cv2
import numpy as np


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
    method = "OSNet 512D / BoT-SORT"

    def __init__(self, model_path, history_size=10):
        path = Path(model_path)
        if not path.is_file():
            raise RuntimeError(f"OSNet TensorRT 엔진이 없습니다: {path}")
        if path.suffix != ".engine":
            raise RuntimeError(f"OSNet은 TensorRT .engine만 지원합니다: {path}")
        self.net = _TensorRTBackend(path)
        self.backend = "TensorRT FP16"
        self.gallery = deque(maxlen=max(1, int(history_size)))
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
            rgb = cv2.cvtColor(cv2.resize(crop, (128, 256)), cv2.COLOR_BGR2RGB)
            tensor = rgb.astype(np.float32) / 255.0
            tensor = (tensor - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
            tensor = np.ascontiguousarray(tensor.transpose(2, 0, 1)[None])
            feature = self.net.infer(tensor).reshape(-1).astype(np.float32)
            norm = np.linalg.norm(feature)
            if feature.size != 512 or not np.isfinite(feature).all() or norm <= 0:
                raise RuntimeError("OSNet 출력은 유한한 512차원 임베딩이어야 합니다")
            return feature / norm
        finally:
            self.elapsed_ms = (time.monotonic() - started) * 1000

    def remember(self, descriptor):
        if descriptor is not None:
            self.gallery.append(descriptor.astype(np.float32, copy=True))

    def similarity(self, descriptor):
        if descriptor is None or not self.gallery:
            return None
        return max(float(np.dot(saved, descriptor)) for saved in self.gallery)

    def close(self):
        self.net.close()
