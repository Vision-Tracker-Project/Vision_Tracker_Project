# AI 카메라·YuNet·SFace·팬틸트 UART 설치 및 실행

## 현재 구현 범위

USB 카메라 출력, YuNet 얼굴 검출, SFace 특징 벡터 추출, 가장 큰 얼굴 선택, 중심 좌표 필터링, 팬·틸트 각도 계산, Jetson UART 전송까지 구현. 특징 벡터는 프레임 처리 중 메모리에서만 사용하며 파일·DB 저장은 미수행. 얼굴 등록 및 유사도 비교는 미구현 상태.

```text
AI/
├── sample.py
├── requirements.txt
├── INSTALL.md
├── ARCHITECTURE.md
├── TESTING.md
├── YUNET.md
├── SFACE.md
├── UART.md
├── models/
│   ├── face_detection_yunet_2023mar.onnx
│   └── face_recognition_sface_2021dec.onnx
├── src/
│   ├── config.py
│   ├── camera/camera_capture.py
│   ├── detection/yunet_detector.py
│   ├── recognition/sface_extractor.py
│   ├── tracking/face_tracker.py
│   ├── communication/protocol.py
│   ├── communication/uart_sender.py
│   ├── workers/video_worker.py
│   └── ui/main_window.py
└── tests/
    ├── test_camera_capture.py
    ├── test_yunet_detector.py
    ├── test_sface_extractor.py
    ├── test_face_tracker.py
    └── test_uart_protocol.py
```

## Jetson 설치

Jetson ARM64에서는 PyPI의 PyQt5 wheel이 없어 소스 빌드 오류 발생 가능. Ubuntu의 시스템 PyQt5 사용 권장.

```bash
sudo apt update
sudo apt install python3-pyqt5
```

Jetson의 시스템 OpenCV와 PyQt5를 공유하도록 가상환경 생성.

```bash
cd ~/work/Vision_Tracker_Project/AI
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

기존 `.venv/pyvenv.cfg`에 아래 설정이 있으면 가상환경 재생성 불필요.

```text
include-system-site-packages = true
```

설치 확인 명령은 다음과 같음.

```bash
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "from PyQt5.QtCore import PYQT_VERSION_STR; print(PYQT_VERSION_STR)"
python3 -c "import serial; print(serial.__version__)"
```

## Qt xcb 오류 확인

pip OpenCV가 Qt 플러그인 경로를 OpenCV 패키지 내부로 변경할 수 있음. 앱 시작 시 PyQt5의 실제 플러그인 경로로 복원하도록 구현.

```bash
python3 -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.PluginsPath))"
```

Jetson Ubuntu의 일반적인 출력 경로는 다음과 같음.

```text
/usr/lib/aarch64-linux-gnu/qt5/plugins
```

`xcb` 오류 지속 시 누락된 공유 라이브러리 확인 가능.

```bash
ldd /usr/lib/aarch64-linux-gnu/qt5/plugins/platforms/libqxcb.so | grep "not found"
```

## 실행

```bash
cd ~/work/Vision_Tracker_Project/AI
source .venv/bin/activate
python3 sample.py
```

`카메라 ON` 선택 시 `/dev/video0`을 `640×480`으로 열고 YuNet 검출, SFace 추출, 팬·틸트 추적, UART 전송 시작. 화면에서 얼굴 박스, 선택 대상, 중심 좌표, 목표 각도, UART 상태와 패킷 확인 가능. `카메라 OFF` 선택 시 처리 중지, UART 연결 종료 및 카메라 해제.

기본 UART 장치는 `/dev/ttyUSB0`, 통신 속도는 115200bps. 다른 장치 사용 시 실행 전에 환경 변수 지정.

```bash
VISION_UART_PORT=/dev/ttyTHS1 python3 sample.py
```

패킷과 추적 설정은 `UART.md` 참고.

## 카메라 확인

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
python3 -m src.camera.camera_checker
```

현재 앱은 카메라 번호 `0`으로 고정. 점유 여부는 아래 명령으로 확인 가능.

```bash
fuser /dev/video0
```

## 테스트

카메라 없이 단위 테스트와 문법 검사 가능.

처음 테스트를 실행하거나 기능별 실행 방법이 필요한 경우 `TESTING.md` 참고.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q sample.py src tests
```

실제 카메라 테스트는 명시적으로 활성화할 때만 실행.

```bash
RUN_CAMERA_TESTS=1 python3 -m unittest discover -s tests -v
```
