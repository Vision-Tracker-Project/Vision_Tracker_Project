"""PC PyQt GUI용 RTP 영상 및 UDP 상태 수신 작업자."""

import socket
import os
import shutil
import subprocess
import tempfile
import threading
import time
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from src.streaming.metadata import MAX_DATAGRAM_SIZE, MetadataError, MetadataOrder, StreamMetadata

def receiver_pipeline(port: int) -> str:
    return (
        f'udpsrc port={port} caps="application/x-rtp,media=video,encoding-name=H264,payload=96" ! '
        "rtpjitterbuffer latency=60 drop-on-latency=true ! rtph264depay ! "
        "h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )

class VideoReceiver(QThread):
    frame_ready = pyqtSignal(object)
    connection_changed = pyqtSignal(bool, str)
    fps_updated = pyqtSignal(float)

    def __init__(self, port: int, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self._lock = threading.Lock()
        self._latest_frame = None
        self._capture = None
        self._process = None

    def take_latest(self):
        with self._lock:
            frame, self._latest_frame = self._latest_frame, None
            return frame

    def stop(self) -> None:
        self.requestInterruption()
        with self._lock:
            capture = self._capture
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        if capture is not None:
            capture.release()

    def run(self) -> None:
        if not cv2.videoio_registry.hasBackend(cv2.CAP_GSTREAMER):
            self._run_external()
            return
        capture = cv2.VideoCapture(receiver_pipeline(self.port), cv2.CAP_GSTREAMER)
        with self._lock:
            self._capture = capture
        if not capture.isOpened():
            capture.release()
            with self._lock:
                self._capture = None
            self.connection_changed.emit(False, "GStreamer 영상 수신기를 열 수 없습니다.")
            return
        self.connection_changed.emit(True, f"영상 UDP {self.port} 수신 중")
        count, started = 0, time.monotonic()
        try:
            while not self.isInterruptionRequested():
                ok, frame = capture.read()
                if not ok:
                    if self.isInterruptionRequested():
                        break
                    self.msleep(20)
                    continue
                with self._lock:
                    self._latest_frame = frame
                count += 1
                now = time.monotonic()
                if now - started >= 1.0:
                    self.fps_updated.emit(count / (now - started))
                    count, started = 0, now
        finally:
            capture.release()
            with self._lock:
                self._capture = None
                self._latest_frame = None

    def _external_command(self, executable):
        # A fixed, four-byte-aligned row size lets stdout carry raw BGR frames.
        return [
            executable, "-q", "udpsrc", f"port={self.port}",
            "caps=application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000",
            "!", "rtpjitterbuffer", "latency=60", "drop-on-latency=true",
            "!", "rtph264depay", "!", "h264parse", "!", "avdec_h264",
            "!", "videoconvert", "!", "videoscale",
            "!", "video/x-raw,format=BGR,width=640,height=480",
            "!", "fdsink", "fd=1", "sync=false",
        ]

    def _run_external(self):
        executable = shutil.which("gst-launch-1.0")
        if not executable:
            self.connection_changed.emit(False, "OpenCV에 GStreamer 지원이 없고 gst-launch-1.0을 찾을 수 없습니다.")
            return
        process = None
        try:
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(
                    self._external_command(executable), stdout=subprocess.PIPE,
                    stderr=errors, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                with self._lock:
                    self._process = process
                if self.isInterruptionRequested():
                    process.terminate()
                    return
                self.connection_changed.emit(False, f"UDP {self.port} 첫 영상 대기 중 (GStreamer)")
                frame_size = 640 * 480 * 3
                pending = bytearray()
                count, started = 0, time.monotonic()
                received = False
                while not self.isInterruptionRequested():
                    chunk = process.stdout.read(frame_size - len(pending))
                    if not chunk:
                        if not self.isInterruptionRequested():
                            errors.seek(0)
                            detail = errors.read(4096).decode("utf-8", errors="replace").strip()
                            self.connection_changed.emit(False, detail or "GStreamer 영상 수신 프로세스가 종료됐습니다.")
                        break
                    pending.extend(chunk)
                    if len(pending) < frame_size:
                        continue
                    frame = np.frombuffer(pending, dtype=np.uint8).reshape(480, 640, 3).copy()
                    pending.clear()
                    with self._lock:
                        self._latest_frame = frame
                    if not received:
                        self.connection_changed.emit(True, f"UDP {self.port} 영상 수신 중 (GStreamer)")
                        received = True
                    count += 1
                    now = time.monotonic()
                    if now - started >= 1.0:
                        self.fps_updated.emit(count / (now - started))
                        count, started = 0, now
        except OSError as error:
            self.connection_changed.emit(False, f"GStreamer 실행 오류: {error}")
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                process.stdout.close()
            with self._lock:
                self._process = None
                self._latest_frame = None

class MetadataReceiver(QThread):
    metadata_ready = pyqtSignal(object)
    connection_changed = pyqtSignal(bool, str)

    def __init__(self, bind_address: str, port: int, stale_seconds: float, parent=None) -> None:
        super().__init__(parent)
        self.bind_address, self.port, self.stale_seconds = bind_address, port, stale_seconds

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.25)
        order = MetadataOrder()
        last_received = 0.0
        stale_reported = True
        try:
            sock.bind((self.bind_address, self.port))
            while not self.isInterruptionRequested():
                try:
                    payload, _ = sock.recvfrom(MAX_DATAGRAM_SIZE + 1)
                    item = StreamMetadata.from_bytes(payload)
                except socket.timeout:
                    if last_received and not stale_reported and time.monotonic() - last_received > self.stale_seconds:
                        self.connection_changed.emit(False, "Jetson 상태 수신 지연")
                        stale_reported = True
                    continue
                except MetadataError:
                    continue
                if order.accept(item):
                    last_received, stale_reported = time.monotonic(), False
                    self.connection_changed.emit(True, "Jetson 상태 연결됨")
                    self.metadata_ready.emit(item)
        except OSError as error:
            self.connection_changed.emit(False, f"상태 포트 오류: {error}")
        finally:
            sock.close()
