# Vision Tracker Project 설치 및 실행 가이드

대상 버전: **Vision_Tracker_Project_GStreamer_PC_Integrated**

이 문서는 PC(Windows), Jetson Orin Nano, STM32F411RE를 같은 프로젝트 버전으로 실행하기 위한 최종 설치 가이드입니다.

---

## 1. 최종 실행 구조

```text
USB Camera
    │
    ▼
Jetson Orin Nano
  ├─ YuNet 얼굴 검출
  ├─ SFace 특징 추출
  ├─ Tracking / Servo Angle 계산
  ├─ UART ───────────────► STM32F411RE
  │                         └─ Pan / Tilt Servo
  │
  └─ H.264 RTP/UDP ──────► Windows PC
                            ├─ GStreamer 직접 수신
                            ├─ PyQt5 GUI
                            └─ Metadata 표시
```

### 실행 명령

PC:

```powershell
py -3.12 main.py
```

Jetson:

```bash
python3 run_jetson.py
```

자동 PC 검색이 실패할 때만:

```bash
python3 run_jetson.py --pc-ip 192.168.0.12
```

> PC와 Jetson 모두 **Vision_Tracker_Project_GStreamer_PC_Integrated** 버전을 사용합니다. Phase1_Phase2 구버전과 섞어 사용하지 않는 것을 권장합니다.

---

# 2. 네트워크 준비

PC와 Jetson을 같은 Wi-Fi 또는 같은 공유기에 연결합니다.

예시:

```text
PC     : 192.168.0.12
Jetson : 192.168.0.200
```

Jetson IP 확인:

```bash
hostname -I
```

Windows PC IP 확인:

```powershell
ipconfig
```

사용 포트:

| 용도 | 프로토콜 | 포트 |
|---|---|---:|
| H.264 영상 | UDP/RTP | 5000 |
| Metadata | UDP | 5001 |
| PC 자동 검색 | UDP Broadcast | 5002 |

Jetson에서 PC 통신 확인:

```bash
ping 192.168.0.12
```

Windows 네트워크 프로필은 가능하면 **개인(Private)** 으로 설정합니다.

필요 시 관리자 PowerShell에서 영상/상태 수신 포트를 허용합니다.

```powershell
New-NetFirewallRule -DisplayName "Vision Tracker UDP" -Direction Inbound -Protocol UDP -LocalPort 5000-5001 -Action Allow -Profile Private
```

---

# 3. Windows PC 설치

## 3-1. Python 확인

이 PC에서는 `python` 명령이 MSYS2 Python을 가리킬 수 있으므로 프로젝트에서는 **Python Launcher의 3.12를 사용하는 것을 권장**합니다.

```powershell
where.exe python
py -0p
```

예를 들어 아래 경로가 보이면 `python` 명령을 프로젝트 실행에 사용하지 않습니다.

```text
C:\msys64\ucrt64\bin\python.exe
```

Python 3.12 확인:

```powershell
py -3.12 --version
py -3.12 -m pip --version
```

`pip`가 없다면:

```powershell
py -3.12 -m ensurepip --upgrade
py -3.12 -m pip install --upgrade pip
```

---

## 3-2. 프로젝트 가상환경 생성

```powershell
cd D:\Vision_Tracker_Project_GStreamer_PC_Integrated\Vision_Tracker_Project\AI
py -3.12 -m venv .venv
```

PowerShell에서 활성화:

```powershell
.\.venv\Scripts\Activate.ps1
```

실행 정책 때문에 활성화가 막히면 활성화하지 않고 아래처럼 직접 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

일반 설치:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PyQt5 확인:

```powershell
python -c "from PyQt5.QtCore import PYQT_VERSION_STR; print(PYQT_VERSION_STR)"
```

---

# 4. Windows GStreamer 설치 확인

현재 통합 버전의 PC 영상 수신은 **OpenCV CAP_GSTREAMER를 사용하지 않습니다.**

따라서 아래처럼 OpenCV에서 `GStreamer: NO`가 나와도 정상입니다.

```powershell
python -c "import cv2; print([x for x in cv2.getBuildInformation().splitlines() if 'GStreamer' in x])"
```

예:

```text
GStreamer: NO
```

PC의 `main.py`가 외부 `gst-launch-1.0`을 subprocess로 직접 실행합니다.

따라서 중요한 것은 **Windows에 GStreamer 실행 파일과 필요한 플러그인이 설치되어 있는지**입니다.

확인:

```powershell
where.exe gst-launch-1.0
gst-launch-1.0 --version
```

필수 플러그인 확인:

```powershell
gst-inspect-1.0 udpsrc
gst-inspect-1.0 rtpjitterbuffer
gst-inspect-1.0 rtph264depay
gst-inspect-1.0 h264parse
gst-inspect-1.0 decodebin
gst-inspect-1.0 videoconvert
gst-inspect-1.0 fdsink
```

하나라도 `No such element or plugin`이 나오면 GStreamer Full 설치 또는 해당 플러그인 패키지가 필요합니다.

GStreamer의 `bin` 폴더가 PATH에 없다면 PATH에 추가합니다. 설치 방식에 따라 예시는 다음과 같습니다.

```text
C:\gstreamer\1.0\msvc_x86_64\bin
```

설치 위치가 다르면 실제 `gst-launch-1.0.exe`가 있는 폴더를 사용합니다.

---

# 5. PC 실행

AI 폴더에서 실행합니다.

가상환경 사용 시:

```powershell
cd D:\Vision_Tracker_Project_GStreamer_PC_Integrated\Vision_Tracker_Project\AI
.\.venv\Scripts\python.exe main.py
```

또는 Python 3.12 직접 실행:

```powershell
py -3.12 main.py
```

정상 동작 시 PC 프로그램은 자동으로 다음 작업을 수행합니다.

```text
PyQt GUI 시작
   ├─ UDP 5000 H.264 영상 수신 대기
   ├─ UDP 5001 Metadata 수신 대기
   └─ UDP 5002 PC Discovery Broadcast 전송
```

**별도의 PowerShell에서 `gst-launch-1.0` 수신 명령을 실행할 필요가 없습니다.**

---

# 6. Jetson 설치

프로젝트 경로 예시:

```bash
~/work/Vision_Tracker_Project_GStreamer_PC_Integrated/Vision_Tracker_Project/AI
```

필수 Ubuntu 패키지 설치:

```bash
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    v4l-utils \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav
```

Jetson은 NVIDIA/Ubuntu 시스템 OpenCV의 GStreamer 지원을 사용해야 하므로 가상환경은 `--system-site-packages`로 생성합니다.

```bash
cd ~/work/Vision_Tracker_Project_GStreamer_PC_Integrated/Vision_Tracker_Project/AI
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy pyserial
```

> Jetson에서는 PC와 달리 pip의 `opencv-python`을 새로 설치하지 않는 것을 권장합니다. `run_jetson.py`는 시스템 OpenCV를 우선 사용하도록 구성되어 있습니다.

OpenCV 확인:

```bash
python3 -c "import cv2; print(cv2.__version__); print(cv2.__file__)"
```

GStreamer 확인:

```bash
gst-launch-1.0 --version
gst-inspect-1.0 nvv4l2h264enc
gst-inspect-1.0 x264enc
```

`nvv4l2h264enc`가 있으면 Jetson 하드웨어 H.264 Encoder를 사용하고, 코드에서는 사용할 수 없는 경우 `x264enc` fallback을 시도합니다.

---

# 7. Jetson 카메라 확인

USB 카메라 연결 후:

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
v4l2-ctl --list-formats-ext
```

현재 프로젝트는 카메라 캡처 시 **MJPG**를 요청합니다.

```text
Camera -> MJPG -> Jetson -> YuNet/SFace -> H.264 -> PC
```

MJPG 적용은 USB 카메라 캡처 지연 감소에 중요합니다.

카메라가 다른 프로그램에서 사용 중인지 확인:

```bash
fuser /dev/video0
```

`No such device`, `VIDIOC_REQBUFS`, `프레임을 읽지 못했습니다` 오류가 발생하면 USB 연결 및 `/dev/video0` 존재 여부부터 확인합니다.

---

# 8. SFace/YuNet 모델 확인

모델 위치:

```text
AI/models/face_detection_yunet_2023mar.onnx
AI/models/face_recognition_sface_2021dec.onnx
```

SFace 모델이 정상 프로젝트와 동일한지 확인할 때:

```bash
sha256sum models/face_recognition_sface_2021dec.onnx
```

현재 정상 확인된 SFace SHA256:

```text
0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79
```

다른 값이 나오면서 `Failed to parse ONNX model` 오류가 발생하면 모델 파일을 다시 복사합니다.

---

# 9. Jetson UART / STM32 연결

기본 UART 설정:

```text
Port : /dev/ttyACM0
Baud : 115200
```

장치 확인:

```bash
ls -l /dev/ttyACM*
```

권한 문제가 있으면:

```bash
sudo usermod -aG dialout $USER
```

이후 로그아웃/로그인 또는 재부팅합니다.

장치명이 다르면 환경 변수로 지정 가능합니다.

```bash
VISION_UART_PORT=/dev/ttyUSB0 python3 run_jetson.py --pc-ip 192.168.0.12
```

---

# 10. 권장 실행 순서

## STEP 1 — STM32 연결

NUCLEO-F411RE를 PC/Jetson 시스템 구성에 맞게 연결하고 펌웨어를 준비합니다.

## STEP 2 — PC 실행

```powershell
cd D:\Vision_Tracker_Project_GStreamer_PC_Integrated\Vision_Tracker_Project\AI
.\.venv\Scripts\python.exe main.py
```

GUI가 뜨면 영상/Metadata 수신 대기 상태입니다.

## STEP 3 — Jetson 실행

```bash
cd ~/work/Vision_Tracker_Project_GStreamer_PC_Integrated/Vision_Tracker_Project/AI
source .venv/bin/activate
python3 run_jetson.py
```

정상 자동 검색 예시:

```text
PC 자동 검색 중... UDP discovery port 5002
PC 자동 검색 완료: 192.168.0.12
Jetson 시작: PC=192.168.0.12, video=5000, metadata=5001, 640x480@20
```

자동 검색이 10~15초 이상 계속되면 기다리지 말고 `Ctrl+C` 후 PC IP를 직접 지정합니다.

```bash
python3 run_jetson.py --pc-ip 192.168.0.12
```

> 현재 Discovery는 네트워크/방화벽 환경에 따라 Broadcast가 차단될 수 있으므로 `--pc-ip`는 공식 fallback 방법으로 사용합니다.

---

# 11. 영상이 나오지 않을 때

## 상황 A — Metadata는 연결되지만 표시 FPS가 0

예:

```text
Jetson 상태 : 연결됨
UART        : 연결됨
표시 FPS    : 0.0
```

이 경우 Jetson 처리 자체보다 **PC GStreamer 영상 수신 경로**를 먼저 확인합니다.

PC:

```powershell
gst-launch-1.0 --version
gst-inspect-1.0 rtph264depay
gst-inspect-1.0 h264parse
gst-inspect-1.0 decodebin
```

Windows 방화벽의 UDP 5000 허용 여부도 확인합니다.

Jetson에서 PC IP가 정확한지 확인합니다.

```bash
python3 run_jetson.py --pc-ip 192.168.0.12
```

## 상황 B — `OpenCV GStreamer: NO`

PC 통합 버전에서는 **문제가 아닙니다.**

PC는 OpenCV GStreamer backend가 아니라 `gst-launch-1.0`을 직접 실행합니다.

## 상황 C — `GStreamer(gst-launch-1.0)를 찾을 수 없습니다`

PC의 GStreamer `bin` 경로를 PATH에 추가한 뒤 새 PowerShell을 엽니다.

```powershell
where.exe gst-launch-1.0
```

---

# 12. STM32 빌드/다운로드

STM32 폴더:

```powershell
cd D:\Vision_Tracker_Project_GStreamer_PC_Integrated\Vision_Tracker_Project\STM32
```

Makefile의 Toolchain 경로를 먼저 확인합니다.

현재 기본값:

```text
C:\arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi
```

빌드:

```powershell
make
```

성공하면 다음 파일이 생성됩니다.

```text
rom_0x08000000.elf
rom_0x08000000.bin
```

보드 Flash:

```powershell
make run
```

`Error: No debug probe detected.`가 나오면 컴파일 문제가 아니라 **ST-LINK 인식 문제**입니다.

확인:

```powershell
STM32_Programmer_CLI.exe -l
STM32_Programmer_CLI.exe -c port=SWD
```

NUCLEO USB 케이블, ST-LINK 드라이버, STM32CubeProgrammer 인식 상태를 확인합니다.

`unused variable 'action'`은 warning이며 현재 빌드 실패 원인은 아닙니다.

---

# 13. 빠른 실행 요약

## Windows PC — 최초 1회

```powershell
cd D:\Vision_Tracker_Project_GStreamer_PC_Integrated\Vision_Tracker_Project\AI
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
gst-launch-1.0 --version
gst-inspect-1.0 rtph264depay
```

## Windows PC — 평소 실행

```powershell
.\.venv\Scripts\python.exe main.py
```

## Jetson — 최초 1회

```bash
cd ~/work/Vision_Tracker_Project_GStreamer_PC_Integrated/Vision_Tracker_Project/AI
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy pyserial
```

## Jetson — 평소 실행

자동 검색:

```bash
source .venv/bin/activate
python3 run_jetson.py
```

자동 검색 실패 시:

```bash
python3 run_jetson.py --pc-ip 192.168.0.12
```

---

# 14. 최종 체크리스트

- [ ] PC와 Jetson이 같은 네트워크에 연결됨
- [ ] PC IP 확인 완료
- [ ] Jetson IP 확인 완료
- [ ] PC Python 3.12 사용
- [ ] PC PyQt5 설치 완료
- [ ] PC `gst-launch-1.0` 실행 가능
- [ ] `rtph264depay`, `h264parse`, `decodebin` 플러그인 확인
- [ ] Jetson `/dev/video0` 확인
- [ ] 카메라 MJPG 지원 확인
- [ ] Jetson GStreamer 확인
- [ ] SFace/YuNet 모델 파일 존재
- [ ] `/dev/ttyACM0` 또는 실제 UART 장치 확인
- [ ] PC에서 `main.py` 먼저 실행
- [ ] Jetson에서 `run_jetson.py` 실행
- [ ] 자동 Discovery 실패 시 `--pc-ip <PC_IP>` 사용

