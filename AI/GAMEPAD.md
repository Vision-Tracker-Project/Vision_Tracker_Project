# 게임패드 차량 제어

YOLO 사람 추적 기준 브랜치와 게임패드 차량 제어를 통합했다. TIM2의
PA0/PA1 팬·틸트 출력과 TIM3의 PC6/PC7 차량 PWM은 서로 독립적이며, 하나의
USART2 공통 파서가 두 프로토콜을 처리한다.

## 실행

`AI/`에서 실행한다. 기본값은 **dry-run**이다. `--uart`가 없으면 `serial.Serial`을 생성하거나 직렬 포트를 열지 않는다. 기본 dry-run은 입력 장치도 열지 않고 정지 패킷을 기록한다. Ctrl+C로 종료한다.

```bash
python -m src.control
python -m unittest tests.test_vehicle_control tests.test_uart_protocol -v
```

Jetson에서 가상환경에 `evdev`를 설치하고 입력 진단을 실행한다. 진단 모드에서는 UART 사용을 거부한다.

```bash
python -m pip install evdev pyserial
python -m src.control --diagnose
```

진단의 `type=1` 이벤트에서 실제 A/B/LB/RB 코드를 확인한다. `gamepad.example.json`을 복사한 뒤 `buttons`를 다음 키의 **측정한 정수 코드**로 채운다: `enable`=A, `stop`=B, `slower`=LB, `faster`=RB. 빈 매핑은 합성 테스트·진단용이며 실제 게임패드 주행은 비활성이다. 숫자 예시를 제공하지 않는 것은 미확인 코드를 사실로 오인하지 않도록 하기 위함이다.

```bash
python -m src.control --gamepad --config gamepad.local.json
# 실제 연결을 확인한 후에만 사용: 이 명령은 UART를 연다.
python -m src.control --gamepad --config gamepad.local.json --uart /dev/ttyTHS1
# YOLO 웹 카메라와 함께 사용. 동일 프로세스의 UART 소유자는 하나다.
python main.py --gamepad --config gamepad.local.json --uart /dev/ttyTHS1
```

웹 통합 실행의 실제 UART도 `--uart 경로`가 필요하다. 과거
`VISION_UART_PORT` 환경 변수만으로 UART를 열던 동작은 명시적 선택 방식으로
변경했다. 독립 CLI와 웹 서버를 동시에 실행해 같은 UART를 열지 않는다. 영상
작업자가 표시하는 서보 전송 여부는 메일박스 접수를 의미하며 하드웨어 수신
확인은 아니다.

장치명과 HAT X/Y 지원으로 자동 탐색한다. `device.vendor`, `device.product`를 JSON 정수로 추가해 제한할 수 있다. 동일 후보가 여러 개면 후보의 경로·식별 정보를 기록하고 **선택을 거부**한다. `--device /dev/input/by-id/...-event-joystick`로 명시적으로 구분할 수 있다. event5 같은 번호는 기본값이 아니다. 장치 접근 권한이 필요하며 진단 오류 로그에서 확인한다.

## 입력·안전 정책

축 최신값은 SYN_REPORT에서 한 쌍으로 확정된다. 위/아래는 전후진, 좌우 단독은 제자리 회전이다. 전후진 대각선은 입력 쪽 바퀴를 `inner_ratio`만큼 낮춘다. 후진 대각선도 후진 경로가 입력 방향으로 휜다는 기준이다. 출력은 -100..100이며 제자리 회전은 `spin_limit`로 제한한다. 기본 속도 단계는 80/90/100%이며 초기 단계는 0(80%)이다. 속도 단계와 초기 단계(0부터)는 JSON 설정이다. 기존 사용자 JSON의 `settings.speeds`가 있으면 기본값보다 우선하므로 `[80, 90, 100]`으로 맞춘다. 제자리 회전 제한은 80%다. 대각선은 속도 단계와 독립적으로 `diagonal_outer`(기본 100%)를 바깥쪽에, 여기에 `inner_ratio`(기본 0.8)를 곱한 80%를 안쪽에 적용한다. 속도 버튼은 직진·후진 단계만 변경하며 기본 제자리 회전은 80%, 대각선은 80/100%로 유지된다. Jetson의 기존 `gamepad.local.json`에서도 `speeds: [80, 90, 100]`, `initial: 0`, `inner_ratio: 0.8`, `spin_limit: 80`, `diagonal_outer: 100`으로 설정해야 한다. 버튼 매핑은 보존한다.

최초 연결·재연결·SYN_DROPPED·UART 오류·제어 루프 지연 후에는 방향 중립, A 해제, A의 **새 누름** 순서가 필요하다. A를 계속 누르고 있던 상태로는 재출발하지 않는다. B는 **소프트웨어 정지 잠금**이며 하드웨어 비상정지가 아니다. B를 놓는 것만으로 풀리지 않으며 B 해제 후 방향 중립·A 해제·새 누름으로 재활성화한다. A 해제와 B 누름은 SYN_REPORT 전에도 출력을 억제한다.

입력 이벤트가 없다는 사실은 연결 해제가 아니다. 누름 상태는 유지하고 50 ms마다 현재 제어 상태를 전송한다. 제거·EOF·읽기 오류·hangup은 정지와 재탐색으로 이어진다. SYN_DROPPED부터 다음 SYN_REPORT까지 이동을 억제하고 ioctl 상태 조회로 재동기화한다. 실제 입력 루프는 프레임 처리와 독립된 스레드에서 실행한다.

`ControlService`만 UART를 열고 쓴다. 카메라는 최신 서보 패킷 한 묶음만
메일박스에 넣는다. 카메라 ON/OFF 또는 영상 작업자 오류는 차량 제어를 중단하지
않는다. UART 쓰기는 50 ms timeout이며 제어 경로에서는 무한 대기 가능성이
있는 flush를 사용하지 않는다. 별도 heartbeat 송신 스레드는 없다. 제어 루프가
멈추면 재전송도 멈춘다. 예외·서버 종료·SIGINT/SIGTERM은 정지 패킷을 최선의
노력으로 전송하고 포트를 닫는다. 전송 실패·프로세스 강제 종료는 STM32
watchdog이 담당한다. OS/USB 버퍼 지연까지 실시간 보장하는 구조는 아니므로
실제 지연 측정이 필요하다.

## UART 프로토콜 v1

115200 baud, 8N1, 흐름 제어 없음. 차량 명령과 heartbeat는 동일한 **8바이트 완전 프레임**이다.

| 바이트 | 필드 | 값 |
|---|---|---|
| 0 | 시작 | AA |
| 1 | 대상 ID | 10 (차량) |
| 2 | 명령 ID | 02 (좌우 출력 설정/갱신) |
| 3 | payload 길이 | 02 |
| 4 | 왼쪽 | signed int8, 2의 보수, -100..100 |
| 5 | 오른쪽 | signed int8, 2의 보수, -100..100 |
| 6 | CRC | 바이트 1..5의 CRC-8, poly=07, init=00, refin/refout=false, xorout=00 |
| 7 | 끝 | 55 |

각 출력 0은 해당 채널 coast다. (0,0)은 전체 정지다. 별도 enable 비트는 없다. 유효한 차량 프레임만 250 ms watchdog을 갱신한다. 서보는 기존 6바이트 `AA target 01 angle sum 55` 그대로이며 target=01/02, angle=0..180이다. 차량 CRC와 서보 합계 체크섬은 서로 다르다.

공통 파서는 분할·연속 수신을 지원한다. 잘못된 길이·명령·범위·CRC·tail이면 창을 1바이트씩 옮겨 재동기화한다. 잘못된 패킷은 watchdog을 연장하지 않는다. ISR은 SR/DR을 읽어 128바이트 ring buffer에 넣는다. UART 오류 또는 overflow는 버퍼·부분 패킷을 폐기하고 정지한다. 파싱·서보 콜백은 메인 문맥에서 처리한다.

## STM32 / NUCLEO-F411RE

사용자가 보드를 NUCLEO-F411RE로 확인했다. MCU STM32F411RE는 LQFP64이며 아래 핀은 ST morpho로 노출된다. 커넥터는 보드 실크와 해당 리비전 회로도도 대조한다.

| 용도 | MCU | Morpho | L298N |
|---|---|---|---|
| 왼쪽 PWM | PC6 AF2 / TIM3 CH1 | CN10-4 | ENA |
| 오른쪽 PWM | PC7 AF2 / TIM3 CH2 | CN10-19 | ENB |
| 왼쪽 방향 | PC2, PC3 | CN7-35, CN7-37 | IN1, IN2 |
| 오른쪽 방향 | PC4, PC5 | CN10-34, CN10-6 | IN3, IN4 |
| 기존 서보 | PA0, PA1 | CN7-28, CN7-30 | 변경 없음 |

전진은 각각 IN1/IN2=1/0, IN3/IN4=1/0이다. `VEHICLE_LEFT_INVERT`, `VEHICLE_RIGHT_INVERT`를 1로 정의하면 장착 방향을 보정한다.

현재 `clock.c`: HSI 16 MHz / PLLM 8 × PLLN 192 / PLLP 4 = SYSCLK/HCLK 96 MHz. APB1 분주 2로 PCLK1=48 MHz, TIM3=96 MHz. TIM3 PSC=0, ARR=4799로 기본 20 kHz다. 두 CCR은 공통 주파수·독립 듀티이며 preload를 함께 갱신한다. PWM 기본 주파수를 10 kHz에서 20 kHz로 변경했다. 발열·파형·모터 동작은 실측해 확인한다. `VEHICLE_PWM_HZ`는 1~20 kHz 범위에서 설정 가능하다. 주파수는 실제로 `96 MHz/(ARR+1)`이다.

`vehicle.h`의 기본값은 가속 100 %포인트/초, 방향 전환 대기 100 ms, watchdog 250 ms다. 반전 시 즉시 0으로 낮추고 대기 후 반대 방향으로 가속한다. 정지 후에도 마지막 방향과 0 시각을 유지해 빠른 재누름으로 반전 대기를 우회하지 않는다. 정지·watchdog은 가속 램프를 거치지 않는다. SysTick도 별도로 PWM 출력을 차단하므로 메인 루프 정지 시에도 차단한다(인터럽트 자체가 정지하면 보장하지 못함).

부팅 초기 출력은 비활성이다. **Enable=0은 coast이며 물리적 즉시 제동이 아니다.** 브레이크 정책은 구현·활성화하지 않았다. 전원 인가부터 MCU 초기화 전까지의 비활성 보장은 EN 외부 pull-down 등 하드웨어가 담당해야 한다.

## 팬·틸트 통합

`servo.c`가 `Vehicle_Servo_Command(target, angle)`를 strong 정의하여 공통 파서의
서보 프레임을 TIM2에 적용한다. `TIM2_Servo_Init()`와 `Vehicle_HW_Init()`는 둘 다
부팅 때 초기화한다. `USART2_IRQHandler`와 RX ring buffer는 하나만 사용하며,
과거 `Packet_Receive()`와 문자열 명령 경로는 제거했다. 서보 콜백은 ISR이 아닌
메인 루프에서 실행되고 차량 watchdog을 갱신하지 않는다. 전체 형식은
[UART_PROTOCOL.md](UART_PROTOCOL.md)를 참고한다.

## 검증 및 연결 전 확인

`python -m unittest tests.test_vehicle_control tests.test_gamepad_device tests.test_uart_protocol -v`는 합성 입력, 가짜 UART·시간, 실제 `STM32/vehicle.c`를 호스트 GCC로 컴파일한 DLL/공유 라이브러리를 사용한다. GCC가 없으면 C 테스트는 skip이다. `python -m unittest discover -s tests -v`, `python -m compileall -q main.py src tests`는 기존 전체 테스트와 문법 검사다. `STM32/`의 `make`는 펌웨어 빌드만 한다. **`make run`은 업로드 명령이므로 이 작업에서는 실행하지 않았다.**

2026-09-08 Windows 검증: 차량·장치 어댑터·기존 UART 테스트 27개 통과, Python compileall 통과, ARM GNU 15.2.1 펌웨어 빌드·링크 통과. 전체 discover는 기존 카메라·추적·SFace·YuNet 테스트 4개 모듈이 현재 Python의 `cv2`/`numpy` 미설치로 import 실패했다. 실제 Linux evdev, Qt GUI 실행, 전기적 PWM·모터 동작은 이 Windows 환경에서 검증하지 않았다. MSYS2 호스트 GCC의 DLL 경로 충돌을 피하도록 C 테스트는 해당 GCC의 bin을 자식 프로세스 PATH 앞에 둔다.

RX 버퍼는 수신 시각도 저장한다. watchdog은 메인에서 늦게 파싱한 시각이 아니라 유효 프레임의 마지막 바이트 수신 시각을 사용하며, 이미 만료한 버퍼 데이터는 폐기한다. 반전 대기는 실제 정지 적용 시각을 사용한다.

하드웨어 팀과 확인할 항목: 측정한 버튼 코드, ENA/ENB 점퍼 제거와 비활성 pull-down, 공통 GND·전압 레벨·모터 전원/전류 및 역기전력 보호, 좌우 극성과 실제 coast 거리, 20 kHz 발열·파형·반전 대기 시간, 게임패드 제거/USB UART 제거/Jetson 루프 정지 시 차단 시간. Jetson GPIO UART를 PA2/PA3에 직접 연결할 경우 Nucleo의 ST-LINK VCP 연결 solder bridge와 충돌 여부를 해당 보드 리비전 회로도로 확인한다. 실제 모터 구동·업로드는 수행하지 않았다.

근거: [ST DS10314, 핀·AF 표](https://www.st.com/resource/en/datasheet/stm32f411re.pdf), [ST RM0383, RCC/TIM3](https://www.st.com/resource/en/reference_manual/dm00119316.pdf), [ST UM1724, Nucleo morpho·USART2 연결](https://www.st.com/resource/en/user_manual/um1724-.pdf), [ST L298 데이터시트](https://www.st.com/resource/en/datasheet/l298.pdf).
