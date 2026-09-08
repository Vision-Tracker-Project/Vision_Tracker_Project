# Phase 1 + Phase 2 리팩토링

## 실행 구조

### PC

```bash
cd AI
python main.py
```

`main.py` 하나가 다음을 모두 수행한다.

- PyQt GUI 실행
- H.264/RTP UDP 영상 수신 시작
- UDP 메타데이터 수신 시작
- Jetson이 PC IP를 찾을 수 있도록 Discovery 브로드캐스트 송신

별도 `stream_receiver.py` 실행은 필요하지 않다.

### Jetson

```bash
cd AI
python run_jetson.py
```

`run_jetson.py`는 먼저 PC Discovery 브로드캐스트를 수신해 송신자 IPv4 주소를 자동으로 얻은 뒤, 그 IP로 H.264 영상과 메타데이터를 전송한다.

정상 예시:

```text
PC 자동 검색 중... UDP discovery port 5002
PC 자동 검색 완료: 192.168.0.12
Jetson 시작: PC=192.168.0.12, video=5000, metadata=5001, 640x480@20
```

## 수동 IP fallback

자동 탐색이 방화벽/VLAN 때문에 동작하지 않을 때만 아래 중 하나를 사용한다.

```bash
python run_jetson.py --pc-ip 192.168.0.12
```

또는

```bash
VISION_STREAM_HOST=192.168.0.12 python run_jetson.py
```

우선순위는 `--pc-ip` > `VISION_STREAM_HOST` > 자동 검색이다.

## 포트

- UDP 5000: H.264 RTP 영상
- UDP 5001: 메타데이터
- UDP 5002: PC 자동 검색 Discovery

PC와 Jetson은 같은 LAN/Wi-Fi 브로드캐스트 도메인에 있어야 한다. Windows 방화벽이 Python의 UDP 통신을 차단하면 Python에 사설 네트워크 통신 권한을 허용해야 한다.

## Windows 영상 수신 변경

Windows의 일반 `opencv-python`은 `GStreamer: NO`인 경우가 많으므로 PC 영상 수신은
`cv2.CAP_GSTREAMER`를 사용하지 않는다. `main.py`가 PATH의 `gst-launch-1.0`을 직접
실행하고 RTP/H.264를 디코딩한 BGR 프레임을 PyQt GUI에 전달한다.

PC에서 다음 명령이 동작해야 한다.

```powershell
gst-launch-1.0 --version
gst-inspect-1.0 rtph264depay
gst-inspect-1.0 h264parse
```

사용자는 별도의 영상 수신 PowerShell 창을 열 필요 없이 다음만 실행한다.

```powershell
py -3.12 main.py
```
