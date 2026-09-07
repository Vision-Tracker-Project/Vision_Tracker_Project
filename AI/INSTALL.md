# Vision Tracker Project 통합 설치 및 실행 가이드

이 문서는 **Jetson Orin Nano(영상 처리/송신)** 와 **Windows PC(PyQt5 GUI/영상 수신)** 를 하나의 Git 저장소에서 설치하고 실행하기 위한 통합 가이드입니다.

> **핵심 구조**
>
> PC와 Jetson은 서로 다른 `AI` 폴더를 관리하지 않습니다. 두 장치 모두 같은 GitHub Repository의 같은 Branch를 clone/pull하고, 실행 진입점만 다르게 사용합니다.
>
> - Branch: `sehyung.stm32.servo.control`
> - Jetson 실행: `python3 jetson_main.py`
> - Windows PC 실행: `main.py`
> - 영상: UDP `5000`
> - Tracking/상태 데이터: UDP `5001`
> - UART: `115200 bps`

```text
                         GitHub
              sehyung.stm32.servo.control
                    /             \
                git pull         git pull
                  /                 \
         Jetson Orin Nano        Windows PC
              |                       |
        same AI/ source          same AI/ source
              |                       |
       jetson_main.py              main.py
              |                       |
Logitech C270 -> OpenCV -> YuNet/SFace -> Tracking
              |                       ^
              +-- UART -> STM32       |
              |          -> Servo     |
              +-- H.264/RTP/UDP ------+
                    Wi-Fi
```

## 1. 준비물 및 프로젝트 구조

- Jetson Orin Nano + JetPack
- Logitech C270 또는 호환 USB 카메라
- STM32 및 Pan/Tilt Servo (제어 기능 사용 시)
- Windows PC + Python 3.12 64비트
- PC/Jetson이 서로 UDP 통신 가능한 네트워크
- GStreamer
- 아래 ONNX 모델

```text
AI/models/face_detection_yunet_2023mar.onnx
AI/models/face_recognition_sface_2021dec.onnx
```

모델 파일은 Git LFS 포인터가 아니라 실제 ONNX 파일이어야 합니다.

주요 실행 파일:

| 장치 | 실행 파일 | 역할 |
|---|---|---|
| Jetson Orin Nano | `AI/jetson_main.py` | 카메라, AI, Tracking, UART, H.264 송신 |
| Windows PC | `AI/main.py` | 영상/상태 수신 및 PyQt5 GUI |

---

## 2. 동일 Git Branch 받기

### 2.1 Jetson - 처음 설치

```bash
cd ~/work
git clone -b sehyung.stm32.servo.control --single-branch \
https://github.com/Vision-Tracker-Project/Vision_Tracker_Project.git

cd ~/work/Vision_Tracker_Project
git branch --show-current
```

정상 결과:

```text
sehyung.stm32.servo.control
```

이미 Repository가 있다면:

```bash
cd ~/work/Vision_Tracker_Project
git fetch origin
git switch sehyung.stm32.servo.control
git pull origin sehyung.stm32.servo.control
```

### 2.2 Windows PC - 처음 설치

Git Bash:

```bash
cd /d
git clone -b sehyung.stm32.servo.control --single-branch \
https://github.com/Vision-Tracker-Project/Vision_Tracker_Project.git

cd /d/Vision_Tracker_Project
git branch --show-current
```

이미 Repository가 있다면:

```bash
cd /d/Vision_Tracker_Project
git fetch origin
git switch sehyung.stm32.servo.control
git pull origin sehyung.stm32.servo.control
```

> PC와 Jetson 모두 동일한 `AI/` 소스를 받습니다. PC에 `jetson_main.py`가 있고 Jetson에 PC UI 코드가 있어도 정상입니다.

---

## 3. Windows PC 설치

### 3.1 Python 3.12 및 가상환경

PowerShell:

```powershell
py -3.12 --version
cd D:\Vision_Tracker_Project\AI

py -3.12 -m venv .venv-pc
.\.venv-pc\Scripts\python.exe -m pip install --upgrade pip
.\.venv-pc\Scripts\python.exe -m pip install -r requirements.txt

.\.venv-pc\Scripts\python.exe -c "import sys, cv2, numpy, serial; from PyQt5 import QtCore; print(sys.executable); print(cv2.__version__); print(QtCore.PYQT_VERSION_STR)"
```

Windows에서는 `python`, `python3`, `py`가 서로 다른 Python을 가리킬 수 있으므로 가상환경의 Python 경로를 직접 사용하는 것을 권장합니다.

### 3.2 Windows GStreamer

현재 검증된 방식은 **MSYS2 UCRT64 GStreamer**입니다.

MSYS2 UCRT64 터미널:

```bash
pacman -Syu
pacman -S --needed \
  mingw-w64-ucrt-x86_64-gstreamer \
  mingw-w64-ucrt-x86_64-gst-plugins-base \
  mingw-w64-ucrt-x86_64-gst-plugins-good \
  mingw-w64-ucrt-x86_64-gst-plugins-bad \
  mingw-w64-ucrt-x86_64-gst-plugins-ugly \
  mingw-w64-ucrt-x86_64-gst-libav
```

PowerShell에서 PATH 및 플러그인 확인:

```powershell
$env:Path = "C:\msys64\ucrt64\bin;" + $env:Path

gst-launch-1.0 --version
gst-inspect-1.0 udpsrc
gst-inspect-1.0 rtpjitterbuffer
gst-inspect-1.0 rtph264depay
gst-inspect-1.0 h264parse
gst-inspect-1.0 avdec_h264
gst-inspect-1.0 fdsink
```

PC OpenCV의 GStreamer 지원 확인:

```powershell
.\.venv-pc\Scripts\python.exe -c "import cv2; print([x.strip() for x in cv2.getBuildInformation().splitlines() if 'GStreamer' in x])"
```

**현재 PC 수신 코드는 `GStreamer: NO`여도 실행할 수 있습니다.** OpenCV GStreamer backend가 없으면 외부 `gst-launch-1.0`을 사용해 H.264를 디코딩하고 BGR 프레임을 GUI로 전달하는 fallback 경로를 사용합니다.

---

## 4. Jetson Orin Nano 설치

Jetson에서는 JetPack의 **GStreamer 지원 시스템 OpenCV**를 유지하는 것이 중요합니다.

### 4.1 시스템 패키지

```bash
sudo apt update
sudo apt install -y \
    python3-venv \
    python3-numpy \
    python3-serial \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    v4l-utils
```

### 4.2 가상환경

```bash
cd ~/work/Vision_Tracker_Project/AI

python3 -m venv --system-site-packages .venv-jetson
source .venv-jetson/bin/activate
```

Jetson에서는 `pip install -r requirements.txt`를 그대로 실행하여 `opencv-python`으로 시스템 OpenCV를 덮어쓰지 않는 것을 권장합니다.

확인:

```bash
python3 -c "import cv2, numpy, serial; print(cv2.__file__); print(cv2.__version__); print('\n'.join(line for line in cv2.getBuildInformation().splitlines() if 'GStreamer' in line)); print('YuNet:', hasattr(cv2, 'FaceDetectorYN')); print('SFace:', hasattr(cv2, 'FaceRecognizerSF'))"
```

권장 결과:

```text
GStreamer: YES
YuNet: True
SFace: True
```

### 4.3 GStreamer 인코더 확인

```bash
gst-inspect-1.0 nvv4l2h264enc
gst-inspect-1.0 x264enc
gst-inspect-1.0 h264parse
gst-inspect-1.0 rtph264pay
```

`nvv4l2h264enc`를 사용할 수 없으면 현재 송신 코드는 `x264enc` software encoder로 fallback합니다.

### 4.4 카메라 및 UART 확인

```bash
v4l2-ctl --list-devices
ls -l /dev/video*
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

기본 설정:

```text
Camera index : 0
UART         : /dev/ttyACM0
Baud rate    : 115200
```

장치 접근 권한 문제가 있으면:

```bash
sudo usermod -aG video,dialout "$USER"
```

실행 후 다시 로그인합니다.

---

## 5. 네트워크 설정

개발 환경 예시:

| 장치 | IP |
|---|---|
| Jetson | `192.168.0.200` |
| Windows PC | `192.168.0.12` |
| 영상 | UDP `5000` |
| Metadata | UDP `5001` |

> PC IP는 Wi-Fi 환경에 따라 달라질 수 있습니다. 실행 전에 `ipconfig`로 실제 값을 확인하세요.

PC → Jetson:

```powershell
ping 192.168.0.200
```

Jetson → PC:

```bash
ping 192.168.0.12
```

필요한 경우 관리자 PowerShell에서 Private network의 UDP 수신을 허용합니다.

```powershell
New-NetFirewallRule -DisplayName "Vision Tracker UDP" `
  -Direction Inbound -Action Allow -Protocol UDP `
  -LocalPort 5000,5001 -Profile Private -RemoteAddress LocalSubnet
```

---

## 6. GStreamer 영상 단독 테스트

AI와 PyQt를 붙이기 전에 영상 통신부터 검증하면 문제를 분리하기 쉽습니다.

### Windows 수신

```powershell
$env:Path = "C:\msys64\ucrt64\bin;" + $env:Path

gst-launch-1.0 -v udpsrc port=5000 caps="application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=96" ! rtpjitterbuffer latency=60 drop-on-latency=true ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false
```

### Jetson 송신

```bash
cd ~/work/Vision_Tracker_Project/AI
source .venv-jetson/bin/activate

export VISION_STREAM_HOST=192.168.0.12
export VISION_VIDEO_PORT=5000
export VISION_METADATA_PORT=5001

python3 jetson_main.py
```

`VISION_STREAM_HOST`에는 **PC의 실제 IP 주소**를 입력합니다.

```text
export VISION_STREAM_HOST=<192.168.0.12>
```

처럼 `< >`를 넣으면 안 됩니다.

---

## 7. 실제 통합 실행

### STEP 1 - PC 수신 GUI 실행

PowerShell:

```powershell
cd D:\Vision_Tracker_Project\AI

$env:Path = "C:\msys64\ucrt64\bin;" + $env:Path
$env:VISION_VIDEO_PORT = "5000"
$env:VISION_METADATA_PORT = "5001"

.\.venv-pc\Scripts\python.exe main.py
```

GUI에서 **영상 수신 ON**을 누릅니다.

### STEP 2 - Jetson AI/송신 실행

```bash
cd ~/work/Vision_Tracker_Project/AI
source .venv-jetson/bin/activate

export VISION_STREAM_HOST=192.168.0.12
export VISION_VIDEO_PORT=5000
export VISION_METADATA_PORT=5001
export VISION_UART_PORT=/dev/ttyACM0

python3 jetson_main.py
```

전체 데이터 흐름:

```text
[Jetson]
Camera
  ↓
OpenCV
  ↓
YuNet Face Detection
  ↓
SFace Feature Extraction
  ↓
Face Tracking
  ├────────────→ UART → STM32 → Pan/Tilt Servo
  │
  ↓
Processed Frame
  ↓
GStreamer H.264 Encode
  ↓
RTP / UDP :5000
  ↓ Wi-Fi
[Windows]
GStreamer Decode
  ↓
OpenCV/BGR Frame
  ↓
PyQt5 GUI

Tracking Metadata
Jetson ───── UDP :5001 ─────→ Windows
```

---

## 8. 권장 Step-by-Step 테스트 순서

처음부터 전체 시스템을 동시에 디버깅하지 않습니다.

```text
1. PC ↔ Jetson Ping
2. Jetson Camera 확인
3. Jetson GStreamer plugin 확인
4. Windows GStreamer plugin 확인
5. gst-launch-1.0 영상 단독 송수신
6. PC GUI 실행 및 영상 수신
7. YuNet/SFace Detection 확인
8. Tracking 확인
9. Jetson ↔ STM32 UART 확인
10. Pan/Tilt Servo 확인
11. 전체 시스템 통합
```

영상 스트리밍과 UART/STM32 제어를 분리해서 테스트하면 오류 원인을 빠르게 찾을 수 있습니다.

---

## 9. PC 단독 수신 테스트

PC에서 Jetson/카메라 없이 receiver 경로를 테스트할 수 있습니다.

```powershell
cd D:\Vision_Tracker_Project\AI

$env:Path = "C:\msys64\ucrt64\bin;" + $env:Path

.\.venv-pc\Scripts\python.exe -m unittest tests.test_video_receiver tests.test_streaming -v
```

테스트가 `OK`라고 나오더라도 `skipped` 항목이 있는지 함께 확인합니다.

---

## 10. GitHub 코드 업데이트 후 동기화

`sehyung.stm32.servo.control` Branch가 업데이트되면 **PC와 Jetson 양쪽에서 각각 pull**합니다.

Jetson:

```bash
cd ~/work/Vision_Tracker_Project
git switch sehyung.stm32.servo.control
git pull origin sehyung.stm32.servo.control
```

Windows Git Bash:

```bash
cd /d/Vision_Tracker_Project
git switch sehyung.stm32.servo.control
git pull origin sehyung.stm32.servo.control
```

따라서 운영 구조는 다음과 같습니다.

```text
GitHub: sehyung.stm32.servo.control
          /                 \
       git pull           git pull
         /                   \
     Jetson                  PC
        |                     |
   jetson_main.py          main.py
        |                     |
        +------ Wi-Fi --------+
```

---

## 11. 주요 오류 해결

| 증상 | 확인 |
|---|---|
| `ModuleNotFoundError: No module named 'src'` | 반드시 `AI` 폴더에서 실행 |
| `gst-launch-1.0`을 찾을 수 없음 | PC PowerShell PATH에 `C:\msys64\ucrt64\bin` 추가 |
| `no element avdec_h264` | Windows `gst-libav` 설치 |
| `no element h264parse` | `gst-plugins-bad` 설치 확인 |
| 첫 영상 대기가 계속됨 | PC IP, UDP 5000, Jetson 송신 로그 확인 |
| Metadata만 연결됨 | UDP 5001은 정상이나 UDP 5000 영상 경로에 문제 가능 |
| Jetson `GStreamer: NO` | 시스템 OpenCV/JetPack OpenCV 확인 |
| 모델 로딩 오류 | `models/`의 실제 ONNX 파일 확인 |
| UART 오류 | `/dev/ttyACM0`, 케이블, 권한, 115200bps 확인 |
| Servo 미동작 | UART와 Servo 제어를 영상 스트리밍과 분리해 테스트 |

---

## 12. 최종 확인 체크리스트

- [ ] PC와 Jetson 모두 `sehyung.stm32.servo.control` Branch
- [ ] 양쪽 모두 최신 `git pull` 완료
- [ ] PC ↔ Jetson Ping 성공
- [ ] Jetson Camera 인식
- [ ] Jetson OpenCV `GStreamer: YES`
- [ ] Jetson H.264 encoder 확인
- [ ] Windows GStreamer decoder/plugin 확인
- [ ] PC UDP 5000/5001 방화벽 확인
- [ ] `VISION_STREAM_HOST`가 실제 PC IP
- [ ] PC `main.py` 실행
- [ ] Jetson `jetson_main.py` 실행
- [ ] 영상 수신 확인
- [ ] Metadata 수신 확인
- [ ] UART 연결 확인
- [ ] Pan/Tilt Servo 동작 확인

---

## 13. 역할 정리

- **OpenCV**: 카메라 입력, 프레임 처리, AI 결과 처리
- **YuNet/SFace**: 얼굴 검출 및 특징 처리
- **Tracking**: 대상 위치를 기준으로 Pan/Tilt 제어값 계산
- **UART**: Jetson에서 STM32로 제어값 전달
- **STM32**: Servo Pan/Tilt 제어
- **GStreamer**: H.264 압축, RTP 패킷화, UDP 영상 송수신
- **PyQt5**: Windows PC GUI

PC와 Jetson의 소스는 하나의 Repository/Branch에서 함께 관리하고, 장치별 실행 진입점과 환경만 분리합니다.
