# 자주 발생하는 실행 오류

## USB 카메라

### `/dev/video*` 장치 확인

```bash
ls -l /dev/video*
cat /sys/class/video4linux/video0/name
```

정상 권한 예시:

```text
crw-rw----+ 1 root video 81, 0 /dev/video0
```

장치가 없으면 USB 카메라 재연결 후 커널 메시지 확인.

```bash
sudo dmesg --ctime | tail -50
```

커널에는 등록됐지만 장치 파일이 없으면 udev 재처리.

```bash
sudo udevadm trigger --subsystem-match=video4linux
sudo udevadm settle
ls -l /dev/video*
```

### `Permission denied`

현재 사용자 그룹 확인:

```bash
id -nG
```

`video` 그룹이 없으면 사용자 추가 후 로그아웃·로그인.

```bash
sudo usermod -aG video "$USER"
```

현재 터미널에서 임시 반영할 때 사용:

```bash
newgrp video
```

`sudo python3 main.py` 또는 `chmod 666 /dev/video0` 사용 비권장. Qt 환경, 생성 파일 소유권, 재연결 후 권한 초기화 문제 발생 가능.

### 장치 점유

```bash
sudo fuser -v /dev/video0
```

점유 프로세스 확인:

```bash
ps -ww -o pid,ppid,stat,args -p <PID>
```

기존 프로그램을 정상 종료한 뒤 재확인. 정상 종료가 불가능할 때만 종료 신호 전달.

```bash
kill -TERM <PID>
sudo fuser -v /dev/video0
```

`STAT`이 `T`인 중지 프로세스가 계속 점유할 때 마지막 수단으로 강제 종료.

```bash
kill -KILL <PID>
```

### OpenCV 단독 확인

```bash
cd ~/work/Vision_Tracker_Project/AI
.venv/bin/python -c "import cv2; c=cv2.VideoCapture(0,cv2.CAP_V4L2); print('OPEN:',c.isOpened()); ok,f=c.read(); print('READ:',ok,None if f is None else f.shape); c.release()"
```

프로젝트 확인 모듈:

```bash
.venv/bin/python -m src.camera.camera_checker
```

## STM32 UART

### 장치 주소를 찾지 못할 때

여기서 주소는 STM32 메모리 주소가 아니라 Jetson에 생성된 직렬 장치 경로를 의미.

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

- NUCLEO ST-LINK 가상 COM 포트: 주로 `/dev/ttyACM0`
- 별도 USB-UART 어댑터: 주로 `/dev/ttyUSB0`
- 재연결 후 번호 변경 가능: `/dev/ttyACM1`, `/dev/ttyUSB1` 등

장치가 없으면 USB 재연결 후 확인:

```bash
lsusb
sudo dmesg --ctime | tail -50
```

장치 상세 정보:

```bash
udevadm info --query=all --name=/dev/ttyACM0
```

프로젝트 기본값은 `src/config.py`의 `UART_PORT`. 실행할 때만 다른 장치를 지정하려면 환경 변수 사용.

```bash
VISION_UART_PORT=/dev/ttyACM1 .venv/bin/python main.py
```

### `Permission denied`

정상 권한 예시:

```text
crw-rw---- 1 root dialout 166, 0 /dev/ttyACM0
```

현재 사용자 그룹 확인:

```bash
id -nG
```

`dialout` 그룹이 없으면 사용자 추가 후 로그아웃·로그인.

```bash
sudo usermod -aG dialout "$USER"
```

현재 터미널에서 임시 반영할 때 사용:

```bash
newgrp dialout
```

### UART 장치 점유

```bash
sudo fuser -v /dev/ttyACM0
```

AI 프로그램과 UART 단독 테스트를 동시에 실행하지 않도록 주의.

### `No module named serial`

설치 패키지 이름은 `pyserial`, Python import 이름은 `serial`.

```bash
.venv/bin/python -m pip install pyserial
.venv/bin/python -c "import serial; print(serial.__version__)"
```

`pip install serial` 사용 금지.

### UART 단독 에코 확인

AI 프로그램을 종료한 상태에서 실행.

```bash
.venv/bin/python -c "import serial,time; p=serial.Serial('/dev/ttyACM0',115200,timeout=2); time.sleep(0.5); p.reset_input_buffer(); tx=bytes([0xAA,0x01,0x01,0x5A,0x5C,0x55]); p.write(tx); p.flush(); rx=p.read(6); print('TX:',tx.hex(' ')); print('RX:',rx.hex(' ')); print('PASS:',tx==rx); p.close()"
```

정상 결과:

```text
TX: aa 01 01 5a 5c 55
RX: aa 01 01 5a 5c 55
PASS: True
```
