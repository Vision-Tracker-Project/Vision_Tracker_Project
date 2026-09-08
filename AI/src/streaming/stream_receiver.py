"""PC PyQt GUI용 RTP 영상 및 UDP 상태 수신 작업자.

Windows의 pip OpenCV는 일반적으로 GStreamer 백엔드가 비활성화되어 있다.
따라서 영상 수신은 cv2.CAP_GSTREAMER 대신 시스템의 GStreamer 실행 파일을
subprocess로 직접 실행하고, 디코딩된 BGR 프레임을 stdout 파이프로 읽는다.
"""

from collections import deque
import shutil
import socket
import subprocess
import threading
import time

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from src.streaming.metadata import (
    MAX_DATAGRAM_SIZE,
    MetadataError,
    MetadataOrder,
    StreamMetadata,
)


def receiver_command(port: int, width: int, height: int) -> list[str]:
    """RTP/H.264를 받아 고정 크기 BGR raw frame으로 stdout에 출력한다."""
    return [
        "gst-launch-1.0",
        "-q",
        "udpsrc",
        f"port={port}",
        "caps=application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=96",
        "!",
        "rtpjitterbuffer",
        "latency=60",
        "drop-on-latency=true",
        "!",
        "rtph264depay",
        "!",
        "h264parse",
        "!",
        "decodebin",
        "!",
        "videoconvert",
        "!",
        "videoscale",
        "!",
        f"video/x-raw,format=BGR,width={width},height={height}",
        "!",
        "fdsink",
        "fd=1",
        "sync=false",
    ]


def _find_gstreamer() -> str | None:
    """PATH에서 gst-launch 실행 파일을 찾는다."""
    return shutil.which("gst-launch-1.0") or shutil.which("gst-launch-1.0.exe")


class VideoReceiver(QThread):
    connection_changed = pyqtSignal(bool, str)
    fps_updated = pyqtSignal(float)

    def __init__(self, port: int, width: int = 640, height: int = 480, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self.width = width
        self.height = height
        self._lock = threading.Lock()
        self._latest_frame = None
        self._process: subprocess.Popen | None = None
        self._stderr_lines: deque[str] = deque(maxlen=12)
        self._stderr_thread: threading.Thread | None = None

    def take_latest(self):
        with self._lock:
            frame, self._latest_frame = self._latest_frame, None
            return frame

    def stop(self) -> None:
        self.requestInterruption()
        self._terminate_process()

    def _terminate_process(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except Exception:
                    pass

    def _drain_stderr(self, process: subprocess.Popen) -> None:
        """stderr PIPE가 차서 GStreamer가 멈추지 않도록 백그라운드에서 비운다."""
        if process.stderr is None:
            return
        try:
            for raw in iter(process.stderr.readline, b""):
                if not raw:
                    break
                text = raw.decode(errors="replace").strip()
                if text:
                    self._stderr_lines.append(text)
        except Exception:
            pass

    @staticmethod
    def _read_exact(stream, size: int) -> bytes | None:
        """stdout에서 정확히 한 프레임 분량을 읽는다."""
        buffer = bytearray()
        while len(buffer) < size:
            chunk = stream.read(size - len(buffer))
            if not chunk:
                return None
            buffer.extend(chunk)
        return bytes(buffer)

    def run(self) -> None:
        gst_path = _find_gstreamer()
        if not gst_path:
            self.connection_changed.emit(
                False,
                "GStreamer(gst-launch-1.0)를 찾을 수 없습니다. 설치 후 PATH를 확인하세요.",
            )
            return

        command = receiver_command(self.port, self.width, self.height)
        command[0] = gst_path
        frame_size = self.width * self.height * 3
        process = None

        try:
            # Windows에서 콘솔창이 추가로 뜨지 않도록 creationflags를 사용한다.
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=creationflags,
            )
            self._process = process

            self._stderr_thread = threading.Thread(
                target=self._drain_stderr,
                args=(process,),
                name="gstreamer-stderr",
                daemon=True,
            )
            self._stderr_thread.start()

            if process.stdout is None:
                self.connection_changed.emit(False, "GStreamer stdout 파이프를 열 수 없습니다.")
                return

            count = 0
            started = time.monotonic()
            first_frame = True

            while not self.isInterruptionRequested():
                raw = self._read_exact(process.stdout, frame_size)
                if raw is None:
                    if self.isInterruptionRequested():
                        break
                    exit_code = process.poll()
                    detail = " / ".join(self._stderr_lines)
                    if exit_code is None:
                        message = "GStreamer 영상 스트림이 종료되었습니다."
                    else:
                        message = f"GStreamer가 종료되었습니다 (code={exit_code})."
                    if detail:
                        message += f" {detail}"
                    self.connection_changed.emit(False, message)
                    break

                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    self.height, self.width, 3
                )

                if first_frame:
                    self.connection_changed.emit(
                        True,
                        f"영상 UDP {self.port} 연결됨 (GStreamer 직접 수신)",
                    )
                    first_frame = False

                # stdout buffer는 다음 read에서 재사용될 수 있으므로 독립 copy를 저장한다.
                with self._lock:
                    self._latest_frame = frame.copy()

                count += 1
                now = time.monotonic()
                if now - started >= 1.0:
                    self.fps_updated.emit(count / (now - started))
                    count, started = 0, now

        except FileNotFoundError:
            self.connection_changed.emit(
                False,
                "GStreamer 실행 파일을 찾지 못했습니다. gst-launch-1.0이 PATH에 있는지 확인하세요.",
            )
        except Exception as error:
            self.connection_changed.emit(False, f"영상 수신 오류: {error}")
        finally:
            self._terminate_process()
            self._process = None
            with self._lock:
                self._latest_frame = None


class MetadataReceiver(QThread):
    metadata_ready = pyqtSignal(object)
    connection_changed = pyqtSignal(bool, str)

    def __init__(self, bind_address: str, port: int, stale_seconds: float, parent=None) -> None:
        super().__init__(parent)
        self.bind_address = bind_address
        self.port = port
        self.stale_seconds = stale_seconds

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.25)
        order = MetadataOrder()
        last_received = 0.0
        started = time.monotonic()
        stale_reported = False
        try:
            sock.bind((self.bind_address, self.port))
            while not self.isInterruptionRequested():
                try:
                    payload, _ = sock.recvfrom(MAX_DATAGRAM_SIZE + 1)
                    item = StreamMetadata.from_bytes(payload)
                except socket.timeout:
                    baseline = last_received or started
                    if not stale_reported and time.monotonic() - baseline > self.stale_seconds:
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
