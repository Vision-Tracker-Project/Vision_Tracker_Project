"""명령 검증·한글 해석·메모리 기록. 하드웨어 의존성 없음."""

from collections import deque
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class Command(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


ACTIONS = {
    Command.FORWARD: "전진",
    Command.BACKWARD: "후진",
    Command.LEFT: "좌회전",
    Command.RIGHT: "우회전",
}


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: Command


class CommandReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool = True
    instance_id: str
    sequence: int
    command: Command
    action: str
    received_at: datetime
    client_ip: str | None
    hardware_sent: bool = False


class CommandStore:
    """최근 100건 보관. 재시작하면 초기화되며 동시 요청은 잠금으로 정렬."""

    def __init__(self, capacity: int = 100) -> None:
        if capacity < 1:
            raise ValueError("capacity는 1 이상이어야 함")
        self.capacity = capacity
        self.instance_id = uuid4().hex
        self.started_at = datetime.now(timezone.utc)
        self._records: deque[CommandReceipt] = deque(maxlen=capacity)
        self._total = 0
        self._lock = Lock()

    def record(self, command: Command, client_ip: str | None) -> CommandReceipt:
        with self._lock:
            self._total += 1
            receipt = CommandReceipt(
                instance_id=self.instance_id,
                sequence=self._total,
                command=command,
                action=ACTIONS[command],
                received_at=datetime.now(timezone.utc),
                client_ip=client_ip,
            )
            self._records.append(receipt)
            return receipt

    def snapshot(self) -> dict:
        with self._lock:
            history = list(reversed(self._records))
            return {
                "instance_id": self.instance_id,
                "started_at": self.started_at,
                "total_received": self._total,
                "history_capacity": self.capacity,
                "latest_command": history[0] if history else None,
                "history": history,
            }


def handle_command(
    payload: CommandRequest, store: CommandStore, client_ip: str | None
) -> CommandReceipt:
    # API 모델에서 enum 검증 후 이 경계에서 다시 명확한 명령 타입으로 해석.
    command = Command(payload.command)
    receipt = store.record(command, client_ip)
    # TODO(STM32 연동 단계): 검증·해석과 별도의 전송 어댑터 send_to_stm32() 추가 위치.
    # 현재는 호출·전송 함수·UART/CAN/USB 접근이 전혀 없음.
    # 향후 전송 결과는 수신 성공과 별도 상태로 관리할 것.
    return receipt
