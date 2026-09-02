"""pyserial 기반 UART 패킷 전송."""

from typing import Callable, Iterable, Optional

from src.communication.protocol import ServoPacket

try:
    import serial
except ImportError:  # 설치 오류를 실행 시 명확히 전달하기 위한 지연 처리
    serial = None


class UartError(RuntimeError):
    """UART 연결 또는 패킷 전송 오류."""


class UartSender:
    """UART 연결 수명과 연속 패킷 전송 관리."""

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        write_timeout: float = 0.2,
        serial_factory: Optional[Callable] = None,
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.write_timeout = write_timeout
        self._serial_factory = serial_factory
        self._connection = None

    @property
    def is_open(self) -> bool:
        return bool(self._connection is not None and self._connection.is_open)

    def open(self) -> None:
        if self.is_open:
            return
        if self._serial_factory is None:
            if serial is None:
                raise UartError("pyserial이 설치되어 있지 않습니다.")
            factory = serial.Serial
        else:
            factory = self._serial_factory

        try:
            self._connection = factory(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0,
                write_timeout=self.write_timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as error:
            self._connection = None
            raise UartError(f"UART를 열 수 없습니다 ({self.port}): {error}") from error

    def send(self, packets: Iterable[ServoPacket]) -> int:
        if not self.is_open:
            raise UartError(f"UART가 연결되지 않았습니다: {self.port}")
        payload = b"".join(packet.data for packet in packets)
        if not payload:
            return 0
        try:
            written = self._connection.write(payload)
            self._connection.flush()
        except Exception as error:
            self.close()
            raise UartError(f"UART 전송 실패 ({self.port}): {error}") from error
        if written != len(payload):
            self.close()
            raise UartError(
                f"UART 전송 길이 불일치: 요청 {len(payload)} Byte, 전송 {written} Byte"
            )
        return written

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
