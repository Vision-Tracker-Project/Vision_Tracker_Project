# 통합 AI·게임패드 제어 구조

웹 기반 YOLO 사람 추적과 게임패드 차량 제어는 처리 주기와 수명 주기를
분리한다. UART 쓰기만 `ControlService` 한 곳으로 모아 패킷 바이트가 서로
섞이지 않게 한다.

```text
USB 게임패드                       USB 카메라
     │ evdev                        │ 최신 프레임
     ▼                              ▼
Controller 상태기계              YOLO + ReID + PersonTracker
     │ 50 ms 차량 명령              │ 변경된 PAN/TILT 패킷
     │                              ▼
     │                         ServoMailbox
     └───────────────────────────┘
                    │
                    ▼
           ControlService (UART 단일 소유)
                    │
                    ▼
                  STM32
             ┌─────────┴─────────┐
             ▼                   ▼
       TIM2 PAN/TILT          TIM3 + GPIO 차량 모터
```

웹 서버가 시작될 때 제어 서비스가 먼저 시작되고 서버 종료 때 마지막으로
정지한다. 카메라 작업자의 시작/정지는 `ServoMailbox`에만 영향을 주므로 차량은
계속 제어할 수 있다. UART 재연결, 게임패드 재연결, 입력 손실 또는 제어 루프
지연 후에는 방향 중립과 A 버튼의 새 누름이 필요하다.

주요 파일:

| 파일 | 역할 |
|---|---|
| `src/main.py` | CLI 설정을 읽고 통합 FastAPI 앱 실행 |
| `src/control/service.py` | 게임패드 주기 처리, UART 소유, 서보 메일박스 |
| `src/control/state.py` | 차량 방향·속도·안전 상태기계 |
| `src/workers/video_worker.py` | 최신 카메라 프레임의 사람 검출과 팬·틸트 계산 |
| `../WEB/rc_web/vision.py` | 웹 카메라 서비스와 메일박스 연결 |
| `../STM32/vehicle.c` | 공통 스트리밍 패킷 파서와 차량 상태 |
| `../STM32/vehicle_hw.c` | UART ring buffer, watchdog, TIM3 차량 출력 |
| `../STM32/servo.c` | TIM2 팬·틸트 PWM과 공통 파서 콜백 |

프로토콜은 [UART_PROTOCOL.md](UART_PROTOCOL.md), 게임패드 안전 정책과 핀맵은
[GAMEPAD.md](GAMEPAD.md)를 참고한다.
