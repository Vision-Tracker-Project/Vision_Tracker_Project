"""Jetson H.264 인코더를 사용하는 비차단 RTP 송신기."""

import queue
import subprocess
import threading
from typing import Optional
import cv2
import numpy as np

def sender_pipeline(host: str, port: int, width: int, height: int, fps: int, bitrate: int, mtu: int) -> str:
    return (
        "appsrc is-live=true block=false format=time "
        f"caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 ! "
        "videoconvert ! video/x-raw,format=BGRx ! nvvidconv ! "
        "video/x-raw(memory:NVMM),format=NV12 ! "
        f"nvv4l2h264enc bitrate={bitrate} insert-sps-pps=true iframeinterval={fps} ! "
        f"h264parse ! rtph264pay config-interval=1 pt=96 mtu={mtu} ! "
        f"udpsink host={host} port={port} sync=false async=false"
    )

def software_sender_pipeline(host: str, port: int, width: int, height: int, fps: int, bitrate: int, mtu: int) -> str:
    return (
        "appsrc is-live=true block=false format=time "
        f"caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 ! "
        "videoconvert ! queue max-size-buffers=1 leaky=downstream ! "
        f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={max(1, bitrate // 1000)} key-int-max={fps} ! "
        f"rtph264pay config-interval=1 pt=96 mtu={mtu} ! "
        f"udpsink host={host} port={port} sync=false async=false"
    )

def has_hardware_encoder() -> bool:
    try:
        result = subprocess.run(
            ["gst-inspect-1.0", "nvv4l2h264enc"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

class GStreamerSender:
    """제어 루프에서는 최신 프레임만 큐에 넣고 즉시 반환한다."""

    def __init__(self, host: str, port: int, width: int, height: int, fps: int, bitrate: int, mtu: int = 1200) -> None:
        self.software_pipeline = software_sender_pipeline(host, port, width, height, fps, bitrate, mtu)
        self.pipeline = sender_pipeline(host, port, width, height, fps, bitrate, mtu)
        if not has_hardware_encoder():
            self.pipeline = self.software_pipeline
        self.size, self.fps = (width, height), fps
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._started = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None
        self.sent = 0
        self.dropped = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._started.clear()
        self.error = None
        self._thread = threading.Thread(target=self._run, name="h264-sender", daemon=True)
        self._thread.start()
        if not self._started.wait(3.0):
            raise RuntimeError("H.264 송신기 시작 시간이 초과되었습니다.")
        if self.error:
            raise RuntimeError(self.error)

    def publish(self, frame: np.ndarray) -> None:
        if self._stop.is_set():
            return
        copy = frame.copy()
        try:
            self._queue.put_nowait(copy)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self.dropped += 1
            try:
                self._queue.put_nowait(copy)
            except queue.Full:
                self.dropped += 1

    def _open_writer(self):
        writer = cv2.VideoWriter(self.pipeline, cv2.CAP_GSTREAMER, 0, float(self.fps), self.size, True)
        if writer.isOpened():
            return writer
        writer.release()
        self.pipeline = self.software_pipeline
        return cv2.VideoWriter(self.pipeline, cv2.CAP_GSTREAMER, 0, float(self.fps), self.size, True)

    def _run(self) -> None:
        writer = self._open_writer()
        if not writer.isOpened():
            self.error = "하드웨어 및 x264 H.264 송신 파이프라인을 열 수 없습니다."
            self._started.set()
            return
        self._started.set()
        try:
            while not self._stop.is_set():
                try:
                    frame = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                writer.write(frame)
                self.sent += 1
        finally:
            writer.release()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
