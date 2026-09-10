# Jetson–STM32 통합 UART 프로토콜 v1

팬·틸트 서보와 RC 차량은 하나의 USART2 링크를 공유한다. Jetson의
`ControlService`만 포트를 열고 쓰며, YOLO 추적 작업자는 계산한 서보 패킷을
메일박스에 제출한다. 게임패드 입력과 차량 heartbeat는 카메라 ON/OFF와
독립적으로 50 ms 주기로 처리된다.

## 물리 계층

| 항목 | 값 |
|---|---|
| Baud rate | `115200` |
| 데이터 비트 | 8 |
| 패리티 | 없음 |
| 정지 비트 | 1 |
| 흐름 제어 | 없음 |
| 바이트 순서 | 표에 표시된 순서 그대로 |

모든 프레임은 `0xAA`로 시작하고 `0x55`로 끝난다. 대상 ID `0x01`,
`0x02`는 기존 6바이트 서보 형식이고 `0x10`은 8바이트 차량 형식이다.

## 팬·틸트 서보 프레임

| 바이트 인덱스 | 필드 | 값 |
|---:|---|---|
| 0 | HEADER | `0xAA` |
| 1 | TARGET_ID | PAN `0x01`, TILT `0x02` |
| 2 | ACTION | 각도 설정 `0x01` |
| 3 | ANGLE | `0x00`∼`0xB4` (0∼180도) |
| 4 | CHECKSUM | `(TARGET_ID + ACTION + ANGLE) & 0xFF` |
| 5 | TAIL | `0x55` |

PAN 90도 예시:

```text
AA 01 01 5A 5C 55
```

서보 프레임은 차량 watchdog을 갱신하지 않는다. 유효한 프레임은 공통 파서가
메인 루프 문맥에서 `TIM2_CH1`(PAN) 또는 `TIM2_CH2`(TILT)에 적용한다.

## RC 차량 프레임

| 바이트 인덱스 | 필드 | 값 |
|---:|---|---|
| 0 | HEADER | `0xAA` |
| 1 | TARGET_ID | 차량 `0x10` |
| 2 | COMMAND_ID | 좌·우 출력 설정/heartbeat `0x02` |
| 3 | PAYLOAD_LENGTH | `0x02` |
| 4 | LEFT | signed int8, 2의 보수, `-100`∼`100` |
| 5 | RIGHT | signed int8, 2의 보수, `-100`∼`100` |
| 6 | CRC8 | 바이트 1∼5의 CRC-8 |
| 7 | TAIL | `0x55` |

CRC 파라미터:

| 항목 | 값 |
|---|---|
| 다항식 | `0x07` |
| 초기값 | `0x00` |
| 입력/출력 반전 | false / false |
| 최종 XOR | `0x00` |

정지/heartbeat 예시:

```text
AA 10 02 02 00 00 C8 55
```

`LEFT=0`, `RIGHT=0`은 양쪽 모터 coast 정지다. 별도 enable 비트는 없다.
유효한 차량 프레임만 250 ms watchdog을 갱신하며, CRC·길이·범위·tail이
잘못된 프레임은 구동 상태를 갱신하지 않는다.

## 수신 및 동시 동작 규칙

| 구분 | 팬·틸트 | RC 차량 |
|---|---|---|
| 입력원 | YOLO 사람 추적 | USB 게임패드 |
| STM32 출력 | TIM2 CH1/CH2, PA0/PA1 | TIM3 CH1/CH2, PC6/PC7 및 PC2∼PC5 |
| 전송 조건 | 목표 각도가 변경되고 100 ms 제한이 지난 경우 | 현재 상태를 50 ms마다 전송 |
| 카메라 OFF 영향 | 서보 전송 중단 | 영향 없음 |
| 안전 제한 | 각도 0∼180 검증 | 250 ms watchdog, 반전 대기, 가속 램프 |

USART2 ISR은 수신 바이트와 수신 시각만 128바이트 ring buffer에 저장한다.
공통 스트리밍 파서는 분할 프레임, 연속 프레임, 두 종류가 섞인 입력을 처리하며
오류 시 한 바이트씩 이동해 다음 `0xAA`에 재동기화한다. UART 오류나 ring buffer
overflow가 발생하면 차량 출력을 즉시 정지하고 부분 프레임을 폐기한다.
