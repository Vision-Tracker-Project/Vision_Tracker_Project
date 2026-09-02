# AI 카메라 GUI 설치 안내

## 1단계: USB 카메라 PyQt GUI

현재 AI 모듈에는 Jetson Orin Nano의 USB 카메라 영상을 PyQt5 GUI에 실시간으로 표시하는 기능이 구현되어 있습니다. YuNet, SFace, 얼굴 인식 및 서보 제어는 아직 포함하지 않습니다.

```text
AI/
├── sample.py               # 실행 진입점
├── requirements.txt
├── src/
│   ├── config.py
│   ├── camera/camera_capture.py
│   ├── workers/video_worker.py
│   └── ui/main_window.py
└── tests/test_camera_capture.py
```

### 환경과 PyQt 선택

확인 당시 Python 3.10.12와 OpenCV 4.11.0은 설치되어 있었지만 PyQt5와 PyQt6는 설치되어 있지 않았습니다. Jetson Ubuntu 시스템 패키지와의 호환성을 고려해 PyQt5를 사용합니다. Linux에서는 V4L2 백엔드로 USB 카메라를 먼저 열고, 실패하면 OpenCV 기본 백엔드로 재시도합니다.

Jetson ARM64에서는 `pip install PyQt5`를 사용하지 않습니다. PyPI에 호환 wheel이 없어 PyQt5 소스 빌드로 전환되고, `qmake` 관련 metadata 오류가 발생합니다. Ubuntu ARM64 저장소의 `python3-pyqt5`를 설치하고 가상환경에서 시스템 패키지를 공유하는 방식이 가장 간단합니다.

### Jetson 설치

먼저 가상환경 밖에서 시스템 PyQt5를 설치합니다.

```bash
sudo apt update
sudo apt install python3-pyqt5
```

그다음 저장소의 `AI` 디렉터리에서 시스템 패키지를 공유하는 가상환경을 생성합니다. 이미 현재 `.venv/pyvenv.cfg`에 `include-system-site-packages = true`가 있다면 다시 만들 필요가 없습니다.

```bash
cd ~/work/Vision_Tracker_Project/AI
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

ARM64에서는 `requirements.txt`의 PyQt5 항목이 자동으로 건너뛰어집니다. PyQt5와 OpenCV import를 확인합니다.

```bash
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "from PyQt5.QtCore import PYQT_VERSION_STR; print(PYQT_VERSION_STR)"
```

PyQt5가 계속 보이지 않으면 가상환경 설정을 확인합니다.

```bash
grep include-system-site-packages .venv/pyvenv.cfg
```

결과가 `false`라면 가상환경을 비활성화하고 `.venv`를 새 이름으로 보관한 다음 `--system-site-packages` 옵션으로 다시 생성합니다. 기존 환경을 삭제할 필요는 없습니다.

### Qt xcb 플러그인 오류

pip의 `opencv-python`은 import 과정에서 Qt 플러그인 경로를 OpenCV 패키지 내부로 변경합니다. 시스템 PyQt5와 함께 사용하면 다음과 같은 오류가 발생할 수 있습니다.

```text
Could not load the Qt platform plugin "xcb" in ".../site-packages/cv2/qt/plugins"
```

애플리케이션 진입점에서 `QApplication`을 만들기 전에 PyQt5의 실제 플러그인 경로를 다시 설정하도록 처리되어 있습니다. 설치 상태는 다음 명령으로 확인할 수 있습니다.

```bash
python3 -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.PluginsPath))"
```

Jetson Ubuntu에서는 일반적으로 `/usr/lib/aarch64-linux-gnu/qt5/plugins`가 출력됩니다. 그래도 `xcb` 오류가 발생하면 누락된 공유 라이브러리를 확인합니다.

```bash
ldd /usr/lib/aarch64-linux-gnu/qt5/plugins/platforms/libqxcb.so | grep "not found"
```

### 실행

`AI` 디렉터리에서 실행합니다.

```bash
python3 sample.py
```

카메라 번호와 해상도를 선택한 다음 **카메라 시작**을 누릅니다. 정지한 뒤 다른 설정으로 다시 시작할 수 있습니다.

### 카메라와 V4L2 확인

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
v4l2-ctl --device=/dev/video0 --all
groups
getent group video
```

`v4l2-ctl`은 `v4l-utils` 패키지에서 제공됩니다. 카메라 권한이 없다면 관리자의 승인을 받아 사용자를 `video` 그룹에 추가하고 다시 로그인합니다.

```bash
sudo usermod -aG video "$USER"
```

카메라가 `/dev/video1` 등으로 잡히면 GUI의 카메라 번호를 변경합니다. 다른 프로세스의 점유 여부는 `fuser /dev/video0`으로 확인할 수 있습니다.

### 테스트

실제 카메라 없이 실행되는 기본 테스트와 문법 검사는 다음과 같습니다.

```bash
cd AI
python3 -m unittest discover -s tests -v
python3 -m compileall -q sample.py src tests
```

카메라가 연결된 환경에서만 하드웨어 테스트를 활성화합니다.

```bash
cd AI
RUN_CAMERA_TESTS=1 python3 -m unittest discover -s tests -v
```

### 다음 단계 연결 위치

다음 단계의 YuNet 검출 파이프라인은 `AI/src/workers/video_worker.py`의 `camera.read()` 직후와 `frame_ready.emit()` 사이에 연결하면 됩니다. 카메라와 UI가 얼굴 검출 구현에 직접 의존하지 않도록 별도 파이프라인 모듈로 추가하는 방식을 권장합니다.
