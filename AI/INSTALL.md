# AI 카메라·YuNet·SFace·팬틸트 UART 설치 및 실행

## 현재 구현 범위

USB 카메라 출력, YuNet 얼굴 검출, SFace 특징 벡터 추출, 가장 큰 얼굴 선택, 중심 좌표 필터링, 팬·틸트 각도 계산, Jetson UART 전송, 최근 60초 프레임 다시보기, 현재 화면 PNG 캡처까지 구현. 특징 벡터와 다시보기 버퍼는 메모리에서만 사용. 얼굴 등록 및 유사도 비교는 미구현 상태.

```text
AI/
├── main.py
├── requirements.txt
├── INSTALL.md
├── ARCHITECTURE.md
├── TESTING.md
├── YUNET.md
├── SFACE.md
├── UART.md
├── REPLAY.md
├── CAPTURE.md
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
│   ├── buffer/frame_buffer.py
│   ├── buffer/frame_buffer_worker.py
│   ├── capture/frame_capture.py
│   ├── workers/video_worker.py
│   └── workers/events.py
└── tests/
    ├── test_camera_capture.py
    ├── test_yunet_detector.py
    ├── test_sface_extractor.py
    ├── test_face_tracker.py
    ├── test_uart_protocol.py
    ├── test_frame_buffer.py
    └── test_frame_capture.py
```

## 설치 및 웹 실행

PyQt GUI는 제거되었습니다. 카메라·추론은 Python 스레드에서 실행하고 웹 화면으로 표시합니다.

```bash
cd ~/work/Vision_Tracker_Project/AI
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py
```

기존 OpenCV가 설치된 가상환경은 재사용 가능합니다. 브라우저에서 `http://<Jetson-WiFi-IP>:8000`으로 접속합니다. 전체 사용법과 FPS 측정 절차는 [WEB/README.md](../WEB/README.md), 부팅 실행은 [AUTOSTART/README.md](../AUTOSTART/README.md)를 참고하세요.

카메라 ON/OFF, 얼굴 검출·특징 추출, 팬틸트 추적, 최근 60초 다시보기는 웹에서 사용합니다. 현재 화면 PNG는 브라우저 다운로드로 접속 기기에 저장합니다. 추적은 기본 OFF이며 AI 모드에서 추적 시작을 눌러야 UART 패킷을 전송합니다.

기본 UART는 `/dev/ttyACM0`, 115200bps. 다른 장치는 `VISION_UART_PORT`로 지정합니다.

## 카메라 확인

권한, 장치 점유, OpenCV 단독 확인 절차는 `TROUBLESHOOTING.md` 참고.

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
python3 -m compileall -q main.py src tests
```

실제 카메라 테스트는 명시적으로 활성화할 때만 실행.

```bash
RUN_CAMERA_TESTS=1 python3 -m unittest discover -s tests -v
```
4
