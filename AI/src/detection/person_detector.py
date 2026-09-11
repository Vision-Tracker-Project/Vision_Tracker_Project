"""YOLO 사람 검출과 BoT-SORT 기반 다중 인물 추적."""

from dataclasses import dataclass
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Optional, Tuple

import cv2
import numpy as np


class PersonDetectorError(RuntimeError):
    pass


class _NumpyBoxes:
    """Ultralytics ByteTrack에 필요한 최소 검출 결과 인터페이스."""

    def __init__(self, xyxy, confidence):
        self.xyxy = np.asarray(xyxy, dtype=np.float32).reshape(-1, 4)
        self.conf = np.asarray(confidence, dtype=np.float32).reshape(-1)
        self.cls = np.zeros(len(self.conf), dtype=np.float32)
        if len(self.xyxy):
            center = (self.xyxy[:, :2] + self.xyxy[:, 2:]) / 2
            size = self.xyxy[:, 2:] - self.xyxy[:, :2]
            self.xywh = np.concatenate((center, size), axis=1)
        else:
            self.xywh = np.empty((0, 4), dtype=np.float32)

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, item):
        return _NumpyBoxes(self.xyxy[item], self.conf[item])


class _TensorRTDetectorBackend:
    """CUDA PyTorch 없이 class 0 전용 TensorRT 엔진을 직접 실행한다."""

    def __init__(self, engine_path):
        try:
            import pycuda.driver as cuda
            import tensorrt as trt
        except ImportError as error:
            raise PersonDetectorError(f"TensorRT 실행 모듈 누락: {error}") from error
        self.cuda = cuda
        self.trt = trt
        cuda.init()
        self.cuda_context = cuda.Device(0).retain_primary_context()
        self.cuda_context.push()
        try:
            logger = trt.Logger(trt.Logger.ERROR)
            with open(engine_path, "rb") as model_file, trt.Runtime(logger) as runtime:
                self.engine = runtime.deserialize_cuda_engine(model_file.read())
            if self.engine is None:
                raise PersonDetectorError("TensorRT 엔진 역직렬화 실패")
            self.context = self.engine.create_execution_context()
            names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]
            self.input_name = next(name for name in names if
                self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT)
            self.output_name = next(name for name in names if
                self.engine.get_tensor_mode(name) == trt.TensorIOMode.OUTPUT)
            self.input_shape = tuple(self.engine.get_tensor_shape(self.input_name))
            self.output_shape = tuple(self.engine.get_tensor_shape(self.output_name))
            if len(self.output_shape) != 3 or self.output_shape[1] != 5:
                raise PersonDetectorError(
                    f"class 0 전용 엔진 출력 형식이 아닙니다: {self.output_shape}"
                )
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
                raise PersonDetectorError("TensorRT 비동기 추론 실패")
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


def _nms(boxes, scores, threshold=0.45):
    if not len(boxes):
        return []
    order = scores.argsort()[::-1]
    keep = []
    while len(order):
        current = int(order[0])
        keep.append(current)
        if len(order) == 1:
            break
        rest = order[1:]
        top_left = np.maximum(boxes[current, :2], boxes[rest, :2])
        bottom_right = np.minimum(boxes[current, 2:], boxes[rest, 2:])
        intersection = np.prod(np.maximum(0, bottom_right - top_left), axis=1)
        area_current = np.prod(np.maximum(0, boxes[current, 2:] - boxes[current, :2]))
        area_rest = np.prod(np.maximum(0, boxes[rest, 2:] - boxes[rest, :2]), axis=1)
        iou = intersection / np.maximum(area_current + area_rest - intersection, 1e-6)
        order = rest[iou <= threshold]
    return keep


@dataclass
class PersonDetection:
    track_id: int
    box: Tuple[int, int, int, int]
    confidence: float
    reid_similarity: Optional[float] = None


class PersonDetector:
    """한 프레임씩 COCO class 0(person)만 검출하며 BoT-SORT 상태를 유지한다."""

    def __init__(self, model_path, confidence=0.35, image_size=640,
                 device="cpu", tracker=None):
        tracker = tracker or str(Path(__file__).with_name("botsort.yaml"))
        path = Path(model_path)
        if not path.is_file():
            raise PersonDetectorError(f"사람 검출 모델 파일을 찾을 수 없습니다: {path}")
        self._tensorrt = path.suffix == ".engine"
        try:
            if self._tensorrt:
                from ultralytics.trackers.bot_sort import BOTSORT
                self.model = _TensorRTDetectorBackend(path)
                self.byte_tracker = BOTSORT(SimpleNamespace(
                    track_high_thresh=0.25, track_low_thresh=0.1,
                    new_track_thresh=0.25, track_buffer=30,
                    match_thresh=0.8, fuse_score=True,
                    gmc_method="sparseOptFlow", with_reid=False,
                    proximity_thresh=0.5, appearance_thresh=0.8, model="auto",
                ))
            else:
                from ultralytics import YOLO
                self.model = YOLO(str(path), task="detect")
        except Exception as error:
            raise PersonDetectorError(f"사람 검출 모델 로드 실패: {error}") from error
        self.confidence = confidence
        self.image_size = image_size
        self.device = device
        self.tracker = tracker
        self.model_name = path.stem
        self.elapsed_ms = 0.0

    def detect(self, frame):
        started = time.monotonic()
        if self._tensorrt:
            detections = self._detect_tensorrt(frame)
            self.elapsed_ms = (time.monotonic() - started) * 1000.0
            return detections
        try:
            result = self.model.track(
                source=frame,
                persist=True,
                tracker=self.tracker,
                classes=[0],
                conf=self.confidence,
                imgsz=self.image_size,
                device=self.device,
                verbose=False,
            )[0]
        except Exception as error:
            raise PersonDetectorError(f"사람 검출 추론 실패: {error}") from error
        self.elapsed_ms = (time.monotonic() - started) * 1000.0
        if result.boxes is None or not len(result.boxes):
            return []

        boxes = result.boxes.xyxy.cpu().numpy()
        scores = result.boxes.conf.cpu().numpy()
        ids = result.boxes.id
        track_ids = ids.int().cpu().tolist() if ids is not None else [-1] * len(boxes)
        detections = []
        for box, score, track_id in zip(boxes, scores, track_ids):
            x1, y1, x2, y2 = box.round().astype(int)
            detections.append(PersonDetection(
                track_id=int(track_id),
                box=(int(x1), int(y1), max(1, int(x2-x1)), max(1, int(y2-y1))),
                confidence=float(score),
            ))
        return detections

    def _detect_tensorrt(self, frame):
        frame_height, frame_width = frame.shape[:2]
        input_height, input_width = self.model.input_shape[2:]
        scale = min(input_width/frame_width, input_height/frame_height)
        resized_width, resized_height = round(frame_width*scale), round(frame_height*scale)
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        pad_x, pad_y = (input_width-resized_width)//2, (input_height-resized_height)//2
        canvas = np.full((input_height, input_width, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y+resized_height, pad_x:pad_x+resized_width] = resized
        tensor = np.ascontiguousarray(
            canvas[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32
        ) / 255.0
        prediction = self.model.infer(tensor)[0].T
        scores = prediction[:, 4]
        accepted = scores >= self.confidence
        prediction, scores = prediction[accepted], scores[accepted]
        if not len(prediction):
            self.byte_tracker.update(_NumpyBoxes([], []), frame)
            return []

        xywh = prediction[:, :4]
        boxes = np.column_stack((xywh[:, 0]-xywh[:, 2]/2, xywh[:, 1]-xywh[:, 3]/2,
                                 xywh[:, 0]+xywh[:, 2]/2, xywh[:, 1]+xywh[:, 3]/2))
        keep = _nms(boxes, scores)
        boxes, scores = boxes[keep], scores[keep]
        boxes[:, [0, 2]] = (boxes[:, [0, 2]]-pad_x)/scale
        boxes[:, [1, 3]] = (boxes[:, [1, 3]]-pad_y)/scale
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, frame_width-1)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, frame_height-1)

        tracks = self.byte_tracker.update(_NumpyBoxes(boxes, scores), frame)
        return [PersonDetection(
            track_id=int(track[4]),
            box=(round(track[0]), round(track[1]),
                 max(1, round(track[2]-track[0])), max(1, round(track[3]-track[1]))),
            confidence=float(track[5]),
        ) for track in tracks]

    def close(self):
        if self._tensorrt:
            self.model.close()

    @staticmethod
    def draw(frame, detections, selected_id=None):
        for person in detections:
            selected = person.track_id == selected_id
            color = (0, 210, 255) if selected else (70, 220, 110)
            x, y, width, height = person.box
            cv2.rectangle(frame, (x, y), (x + width, y + height), color, 3 if selected else 2)
            similarity = "" if person.reid_similarity is None else f" R {person.reid_similarity:.2f}"
            label = f"ID {person.track_id} {person.confidence:.2f}{similarity}"
            cv2.putText(frame, label, (x, max(18, y - 7)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 2, cv2.LINE_AA)
        return frame
