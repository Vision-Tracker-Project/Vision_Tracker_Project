# 팬·틸트 UART 전송

## 처리 흐름

```text
YuNet 얼굴 목록
    ↓
가장 큰 얼굴 선택
    ↓
얼굴 중심 좌표 EMA 필터
    ↓
화면 중심과의 오차 계산
    ↓
팬·틸트 목표 각도 누적 계산
    ↓
PAN/TILT 6바이트 패킷 생성
    ↓
Jetson UART에서 STM32로 연속 전송
```

얼굴 등록·인식 전 단계이므로 화면에서 가장 큰 얼굴을 임시 추적 대상으로 선택. `추적 시작` 전에는 얼굴 검출만 수행하고 각도 계산과 패킷 전송 중지. 얼굴이 없으면 각도 유지 및 패킷 전송 중지.

## 각도 계산 방식

Qt 화면의 PAN·TILT 값은 STM32에서 받은 실제 각도가 아니라 Jetson이 계산한 목표 각도. 같은 값이 패킷의 `PARAM`으로 전송됨.

```text
얼굴 중심 오차
→ Jetson 목표 각도 누적
→ Qt 화면 표시
→ UART 패킷 전송
```

서보 각도 피드백은 현재 사용하지 않음. 서보가 카메라를 움직이면 영상 속 얼굴 중심이 화면 중앙으로 이동하고 각도 변경이 중지되는 구조.

서보가 움직이지 않거나 회전 방향이 반대이면 얼굴 중심 오차가 유지되므로 목표 각도가 계속 누적되어 설정된 최소·최대 각도에서 정지.

## 패킷 형식

각 서보마다 독립된 6바이트 패킷 사용.

| 순서 | 필드 | 값 |
|---|---|---|
| 1 | HEADER | `0xAA` |
| 2 | TARGET_ID | PAN `0x01`, TILT `0x02` |
| 3 | ACTION | 각도 설정 `0x01` |
| 4 | PARAM | 각도 `0x00~0xB4` |
| 5 | CHECKSUM | `(TARGET_ID + ACTION + PARAM) & 0xFF` |
| 6 | TAIL | `0x55` |

90도 PAN 패킷 예시:

```text
AA 01 01 5A 5C 55
```

PAN과 TILT 값 변경 시 6바이트 패킷 두 개를 합친 12바이트를 한 번의 UART 쓰기로 전송. STM32에서는 6바이트 단위로 분리 가능.

## 기본 UART 설정

- 장치: `/dev/ttyACM0`
- 통신 속도: `115200bps`
- 데이터: 8비트
- 패리티: 없음
- 정지 비트: 1비트
- 흐름 제어: 없음

장치 경로가 다른 경우 실행 전에 환경 변수 지정.

```bash
VISION_UART_PORT=/dev/ttyTHS1 python3 main.py
```

USB-UART 장치 확인:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```

접근 권한 오류 시 현재 계정의 `dialout` 그룹 확인.

```bash
groups
ls -l /dev/ttyACM0
```

`dialout` 추가가 필요한 경우:

```bash
sudo usermod -aG dialout $USER
```

변경 후 로그아웃·로그인 필요.

## 방향과 움직임 조정

`src/config.py`에서 아래 값 변경 가능.

- `PAN_INVERTED`, `TILT_INVERTED`: 서보 회전 방향 반전
- `PAN_MIN_ANGLE`, `PAN_MAX_ANGLE`: 팬 안전 범위
- `TILT_MIN_ANGLE`, `TILT_MAX_ANGLE`: 틸트 안전 범위
- `TRACKING_FILTER_ALPHA`: 중심 좌표 반응 속도
- `TRACKING_DEAD_ZONE_RATIO`: 화면 중심의 무동작 영역
- `TRACKING_GAIN`: 오차 대비 각도 변화량
- `TRACKING_MAX_STEP_DEGREES`: 프레임당 최대 각도 변화
- `SERVO_SEND_INTERVAL_SECONDS`: 최소 UART 전송 간격

최초 하드웨어 연결 시 좁은 안전 각도 범위 설정 후 방향 확인 권장.

## Qt 표시 정보

- 필터링된 얼굴 중심 좌표
- 팬·틸트 목표 각도
- UART 연결 또는 오류 상태
- PAN/TILT 패킷 Hex 값
- 현재 프레임에서 실제 전송 여부

UART 연결 실패 시 카메라와 얼굴 검출은 계속 실행. 설정된 재시도 간격마다 자동 재연결 시도.
