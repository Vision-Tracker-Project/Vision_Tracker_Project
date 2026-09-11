# 카메라·팬틸트·차량 통합 자동 실행

`AUTOSTART/install.sh`는 기존 팬·틸트 웹 서비스의 systemd 방식을 사용해
다음 기능을 하나의 `vision-tracker-web.service`로 설치한다.

- 부팅 시 웹 서버와 AI 카메라 자동 시작(포트 8000)
- YOLO 사람 추적 결과로 PAN/TILT 제어
- USB 게임패드로 RC 차량 제어
- 단일 프로세스와 단일 UART 소유자 사용
- 카메라를 꺼도 차량 제어 유지

설치 스크립트는 `AI/.venv`, `AI/venv`, 현재 활성화된 `VIRTUAL_ENV` 순서로
Python 가상환경을 찾는다. 다른 위치라면 설치할 때
`VISION_PYTHON=/절대경로/bin/python`을 지정한다. 탐지된 절대 경로가 systemd
서비스에 저장되므로 부팅 후 가상환경을 수동 활성화할 필요가 없다.

Jetson에 외부 전원이 들어오면 USB를 통해 M4 보드가 켜지고 장치가 열거된다.
systemd가 먼저 시작되더라도 제어 서비스가 게임패드와 UART 연결을 1초마다
재시도하므로 고정 지연 명령은 필요 없다. UART가 연결되면 차량 정지 패킷을 먼저
보낸 뒤 팬 90도와 틸트 27도 초기화 프레임을 한 번의 UART 쓰기로 전송한다. 연결이
끊겼다가 복구되는 경우에도 같은 초기화를 다시 수행한다. 종료 시에는 정지 패킷
전송을 시도하고, USB 전원이 먼저 사라지는 경우에는 M4의 250 ms 차량 watchdog이
출력을 차단한다.

## 최초 설정

측정한 버튼 코드 파일을 만든다. 이 파일은 Git에 포함되지 않는다.

```bash
cd ~/work/Vision_Tracker_Project
cp AI/gamepad.example.json AI/gamepad.local.json
```

`AI/gamepad.local.json`의 `enable`, `stop`, `slower`, `faster`에 실제 A, B,
LB, RB 코드를 입력한다.

가능하면 재부팅 후에도 유지되는 장치 경로를 확인한다.

```bash
ls -l /dev/input/by-id/
ls -l /dev/serial/by-id/
```

게임패드는 기본값 `auto`로 이름과 HAT 축을 기준으로 매번 탐색한다. 따라서
`event6`처럼 재부팅 후 달라지는 번호를 설치 파일에 저장하지 않는다. 현재 확인한
STM32 임시 경로로 설치:

```bash
VISION_UART_DEVICE=/dev/ttyACM2 \
bash AUTOSTART/install.sh
```

가상환경이 `AI/venv`에 있으면 자동으로 인식한다. 프로젝트 밖에 있다면 다음처럼
한 번만 실제 경로를 지정한다.

```bash
VISION_PYTHON=/home/aidl/venv/bin/python \
VISION_UART_DEVICE=/dev/ttyACM2 \
bash AUTOSTART/install.sh
```

고정 `by-id` 경로가 있으면 다음 형식을 권장한다.

```bash
VISION_GAMEPAD_DEVICE=/dev/input/by-id/<gamepad>-event-joystick \
VISION_UART_DEVICE=/dev/serial/by-id/<stm32-uart> \
bash AUTOSTART/install.sh
```

다른 버튼 설정 파일을 쓰는 경우 `VISION_GAMEPAD_CONFIG`도 설치 시 지정한다.
설치 스크립트는 Python 의존성과 버튼 매핑을 검사하고 실제 절대 경로가 들어간
systemd unit을 `/etc/systemd/system/vision-tracker-web.service`에 설치한다.

## 운영 명령

설치가 끝나면 이후에는 Python 명령을 직접 실행하지 않는다.

```bash
sudo systemctl status vision-tracker-web.service
sudo journalctl -u vision-tracker-web.service -n 100 --no-pager
sudo systemctl restart vision-tracker-web.service
sudo systemctl stop vision-tracker-web.service
```

부팅 자동 실행 확인:

```bash
sudo systemctl is-enabled vision-tracker-web.service
sudo systemctl is-active vision-tracker-web.service
```

설정된 장치 경로 확인:

```bash
sudo systemctl cat vision-tracker-web.service
```

장치 번호나 프로젝트 경로를 변경하면 새 환경값으로 `install.sh`를 다시 실행한다.

## 권한과 안전

systemd 서비스에는 `input`, `dialout` 보조 그룹이 지정되어 로그인 세션 없이도
게임패드와 UART에 접근한다. `PrivateDevices=false`이므로 실제 `/dev` 장치가
서비스에 보인다. 같은 UART를 사용하는 `python -m src.control`, 별도 Uvicorn,
시리얼 터미널을 동시에 실행하지 않는다.

게임패드 연결·재연결, UART 재연결 또는 서비스 재시작 후에는 방향 중립, A 버튼
해제, A 버튼 새 누름 순서로 차량을 다시 활성화해야 한다. B 버튼은 소프트웨어
정지 잠금이며 물리적 비상정지를 대체하지 않는다.
