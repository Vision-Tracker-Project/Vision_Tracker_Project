# Vision Tracker Project

Jetson Orin Nano에서 USB 카메라 영상을 처리하고, YuNet/SFace 기반 얼굴 검출·특징 추출과 팬·틸트 추적을 수행한 뒤 STM32로 서보 각도 명령을 전달하는 실시간 비전 트래킹 프로젝트입니다. PC에서는 PyQt GUI로 H.264/RTP 영상을 수신하고 Jetson 처리 상태와 UART 상태를 확인할 수 있습니다.

## 주요 기능

- USB 카메라 입력 및 MJPG 캡처
- YuNet 얼굴 검출
- SFace 특징 벡터 추출
- 가장 큰 얼굴을 기준으로 팬·틸트 목표 각도 계산
- Jetson → STM32 UART 제어 (`115200bps`)
- Jetson → PC H.264/RTP UDP 영상 스트리밍
- Jetson → PC UDP 메타데이터 전송
- PC → Jetson UDP Discovery를 이용한 PC IP 자동 탐색
- Windows PC에서 OpenCV GStreamer backend 없이 시스템 `gst-launch-1.0`을 직접 사용하여 영상 수신

## 시스템 구성

```text
USB Camera
    │
    ▼
Jetson Orin Nano
    ├─ YuNet Face Detection
    ├─ SFace Feature Extraction
    ├─ Face Tracking / Pan-Tilt Calculation
    │
    ├─ UART 115200bps ─────────────► STM32F411RE ─► Pan/Tilt Servo
    │
    └─ H.264 RTP + Metadata / Wi-Fi
                    │
                    ▼
                Windows PC
                    ├─ GStreamer H.264 Decode
                    └─ PyQt GUI
```

## 프로젝트 구조

```text
Vision_Tracker_Project/
├── AI/
│   ├── main.py                     # PC GUI 실행 진입점
│   ├── run_jetson.py               # Jetson headless 실행 진입점
│   ├── requirements.txt
│   ├── INSTALL.md                  # 설치 및 실행 가이드
│   ├── ARCHITECTURE.md
│   ├── TESTING.md
│   ├── UART.md
│   ├── YUNET.md
│   ├── SFACE.md
│   ├── models/
│   │   ├── face_detection_yunet_2023mar.onnx
│   │   └── face_recognition_sface_2021dec.onnx
│   ├── src/
│   │   ├── camera/
│   │   ├── communication/
│   │   ├── detection/
│   │   ├── network/
│   │   ├── recognition/
│   │   ├── streaming/
│   │   ├── tracking/
│   │   ├── ui/
│   │   └── workers/
│   └── tests/
├── STM32/                          # STM32F411RE 펌웨어 및 Makefile
├── .gitignore
└── README.md
```

## 빠른 실행

처음 사용하는 경우 먼저 [`AI/INSTALL.md`](AI/INSTALL.md)를 따라 PC, Jetson, STM32 환경을 준비하세요.

### 1. PC 먼저 실행

Windows PowerShell에서:

```powershell
cd D:\Vision_Tracker_Project\AI
py -3.12 main.py
```

PC 프로그램 하나가 다음 기능을 함께 시작합니다.

- PyQt GUI
- UDP `5000` H.264/RTP 영상 수신
- UDP `5001` 메타데이터 수신
- UDP `5002` PC Discovery 브로드캐스트

별도의 `stream_receiver.py` 또는 별도의 GStreamer PowerShell 창을 실행할 필요가 없습니다.

### 2. Jetson 실행

```bash
cd ~/work/Vision_Tracker_Project/AI
python3 run_jetson.py
```

PC가 먼저 실행 중이고 같은 LAN/Wi-Fi에 있으면 Jetson이 PC IP를 자동 탐색합니다.

자동 탐색이 동작하지 않을 때만 PC IPv4 주소를 직접 지정합니다.

```bash
python3 run_jetson.py --pc-ip 192.168.0.12
```

## 기본 네트워크 포트

| 용도 | 프로토콜 | 기본 포트 |
|---|---|---:|
| H.264/RTP 영상 | UDP | `5000` |
| 상태 메타데이터 | UDP | `5001` |
| PC 자동 탐색 | UDP Broadcast | `5002` |

PC와 Jetson은 같은 LAN/Wi-Fi 브로드캐스트 도메인에 있어야 합니다. Windows Defender Firewall이 Python 또는 UDP 통신을 차단하면 사설 네트워크 통신을 허용해야 합니다.

## 기본 하드웨어 설정

- Jetson: NVIDIA Jetson Orin Nano Developer Kit
- MCU: NUCLEO-F411RE / STM32F411RE
- Camera: USB UVC Camera (개발 환경에서는 Logitech C270 사용)
- Pan/Tilt: 2축 Servo
- Jetson ↔ STM32: UART `115200bps`
- 기본 Jetson UART 장치: `/dev/ttyACM0`
- 기본 영상 크기: `640x480`
- 목표 처리 FPS: `20`

## 실행 전 빠른 확인

PC:

```powershell
py -3.12 --version
gst-launch-1.0 --version
gst-inspect-1.0 rtph264depay
gst-inspect-1.0 h264parse
```

Jetson:

```bash
python3 -c "import cv2; print(cv2.__version__)"
gst-launch-1.0 --version
ls -l /dev/video*
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

## 현재 구현 범위

현재 SFace 특징 벡터는 프레임 처리 중 사용하지만 사용자 얼굴 등록 DB 및 유사도 기반 신원 인식 기능은 구현하지 않았습니다. 추적 대상은 현재 검출된 얼굴 중 가장 큰 얼굴을 기준으로 선택합니다.

PC IP 자동 탐색은 UDP 브로드캐스트를 사용하므로 방화벽, VLAN, AP 설정 등에 따라 동작하지 않을 수 있습니다. 이 경우 `--pc-ip` 옵션을 사용하세요.

## 문서

- [설치 및 실행](AI/INSTALL.md)
- [전체 구조](AI/ARCHITECTURE.md)
- [테스트](AI/TESTING.md)
- [UART 프로토콜](AI/UART.md)
- [YuNet](AI/YUNET.md)
- [SFace](AI/SFACE.md)
- [Phase 1/2 리팩토링](AI/PHASE1_2.md)
