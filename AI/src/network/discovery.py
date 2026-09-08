"""UDP 브로드캐스트를 이용해 Jetson이 PC 스트리밍 목적지 IP를 자동 탐색한다."""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional


DISCOVERY_MAGIC = "VISION_TRACKER_PC_V1"


@dataclass(frozen=True)
class DiscoveryResult:
    host: str
    video_port: int
    metadata_port: int


def _build_payload(video_port: int, metadata_port: int) -> bytes:
    return json.dumps(
        {
            "magic": DISCOVERY_MAGIC,
            "video_port": int(video_port),
            "metadata_port": int(metadata_port),
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _parse_payload(payload: bytes, sender_ip: str) -> Optional[DiscoveryResult]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("magic") != DISCOVERY_MAGIC:
        return None
    try:
        video_port = int(value["video_port"])
        metadata_port = int(value["metadata_port"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (1 <= video_port <= 65535 and 1 <= metadata_port <= 65535):
        return None
    return DiscoveryResult(sender_ip, video_port, metadata_port)


class PcDiscoveryBroadcaster:
    """PC에서 주기적으로 존재를 알린다. Jetson은 패킷의 송신자 IP를 PC IP로 사용한다."""

    def __init__(
        self,
        discovery_port: int,
        video_port: int,
        metadata_port: int,
        interval: float = 1.0,
    ) -> None:
        self.discovery_port = int(discovery_port)
        self.video_port = int(video_port)
        self.metadata_port = int(metadata_port)
        self.interval = max(0.2, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="vision-pc-discovery",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        payload = _build_payload(self.video_port, self.metadata_port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            while not self._stop.is_set():
                try:
                    sock.sendto(payload, ("255.255.255.255", self.discovery_port))
                except OSError:
                    # Wi-Fi가 잠시 끊겨도 GUI 자체는 계속 실행한다.
                    pass
                self._stop.wait(self.interval)
        finally:
            sock.close()


def discover_pc(
    discovery_port: int,
    timeout: Optional[float] = None,
    retry_message_interval: float = 5.0,
) -> DiscoveryResult:
    """Jetson에서 PC 브로드캐스트를 기다리고 송신자 IP를 반환한다.

    timeout=None이면 PC를 찾을 때까지 대기한다.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", int(discovery_port)))
    sock.settimeout(1.0)
    started = time.monotonic()
    last_message = started - retry_message_interval
    try:
        while True:
            now = time.monotonic()
            if timeout is not None and now - started >= timeout:
                raise TimeoutError(f"{timeout:.1f}초 동안 PC를 찾지 못했습니다.")
            if now - last_message >= retry_message_interval:
                print(f"PC 자동 검색 중... UDP discovery port {discovery_port}")
                last_message = now
            try:
                payload, address = sock.recvfrom(2048)
            except socket.timeout:
                continue
            result = _parse_payload(payload, address[0])
            if result is not None:
                return result
    finally:
        sock.close()
