# 팬·틸트 및 차량 UART 전송

통합 실행에서는 `ControlService` 하나만 UART를 소유한다. YOLO 사람 추적은
PAN/TILT 패킷을 메일박스에 넣고, 같은 서비스의 독립 스레드가 게임패드를
읽어 차량 패킷과 함께 순서대로 전송한다. 카메라가 꺼지거나 영상 처리가
느려져도 차량 입력 루프는 계속 동작한다.

전체 바이트 표와 checksum/CRC 규칙은 [UART_PROTOCOL.md](UART_PROTOCOL.md)를
기준으로 한다.

## 실행

기본 실행은 UART를 열지 않는 dry-run이다. 실제 장치에서는 포트와 측정한
게임패드 설정을 명시한다.

```bash
cd ~/work/Vision_Tracker_Project/AI
python3 main.py \
  --gamepad \
  --device /dev/input/by-id/<gamepad>-event-joystick \
  --config gamepad.local.json \
  --uart /dev/serial/by-id/<stm32-uart>
```

`/dev/input/eventN`과 `/dev/ttyACMN`도 사용할 수 있지만 연결 순서에 따라 번호가
바뀔 수 있다. `--uart`를 생략하면 `src/config.py`의 `UART_PORT` 값과 관계없이
통합 제어 서비스는 실제 포트를 열지 않는다.

웹 카메라 시작/정지는 팬·틸트 송신만 시작/정지한다. 차량을 다시 활성화할
필요는 없으며, 차량은 A 버튼을 누르고 있는 동안 게임패드 방향 입력을 따른다.

## UART 소유권

CLI 제어 프로그램과 웹 서버를 동시에 실행해 같은 포트를 열면 안 된다.
통합 웹 실행 하나만 사용한다. 종료 시 서비스는 정지 패킷 전송을 시도한 뒤
포트를 닫는다.
