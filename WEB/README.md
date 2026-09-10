# Jetson Vision Tracker 웹 화면

실시간 영상은 JPEG 한 장씩 최신 프레임을 요청하는 방식입니다. WebRTC는 실제 장비에서 약 2초 영상 지연과 높은 RTT가 확인되어 제거했습니다. 카메라·YOLO 사람 추적·PNG 저장·수동 명령 수신 화면을 제공하며, 실제 차량은 별도의 USB 게임패드로 제어합니다.

## 지연 방지 구조

```text
USB 카메라 전용 스레드 (계속 30 FPS 캡처)
               │ 최신 프레임 한 장만 보관
               ▼
AI 작업자 (YOLO / ReID / 추적 / 박스 표시)
               │ 느리면 중간 프레임 폐기
               ▼
최신 JPEG 한 장 ── HTTP ── 브라우저 canvas
```

카메라 읽기와 추론을 분리했습니다. 추론이 잠깐 느려져도 카메라 드라이버의 과거 프레임을 순서대로 처리하지 않고, 완료 후 가장 최신 프레임으로 이동합니다. 화면에는 순간적인 FPS 감소가 생길 수 있지만 시간이 누적되는 영상 지연은 만들지 않습니다.

YOLO는 사람 클래스만 검출하고 ByteTrack과 appearance ReID로 선택 대상을
유지합니다. 팬·틸트 추적은 각 AI 프레임에서 계산하되 목표 각도가 실제로
변경될 때만 UART 메일박스에 패킷을 제출합니다.

화면에는 카메라 FPS, AI FPS, 브라우저 FPS, AI 처리 시간, 프레임 나이, AI가 건너뛴 프레임 누계가 표시됩니다. `AI 건너뜀` 증가는 의도한 저지연 동작입니다. `프레임 나이`가 계속 증가하지 않고 처리 부하가 끝난 뒤 즉시 낮아지는지를 확인합니다.

## 실행

카메라와 게임패드 차량 제어를 함께 실행하려면 `AI/`의 통합 진입점을 사용한다.
실제 버튼 코드는 먼저 `gamepad.local.json`에 기록해야 한다.

```bash
cd /home/aidl/work/Vision_Tracker_Project/AI
python3 main.py \
  --gamepad \
  --device /dev/input/event6 \
  --config gamepad.local.json \
  --uart /dev/ttyACM2
```

이 프로세스가 UART를 단독 소유한다. 웹에서 카메라를 꺼도 게임패드 차량
제어는 계속 동작한다. `/dev/input/eventN`, `/dev/ttyACMN`보다
`/dev/input/by-id/`, `/dev/serial/by-id/`의 고정 경로 사용을 권장한다.

웹·카메라만 개발할 때는 기존 `WEB/run.sh`를 사용할 수 있지만, 이 경로에는
게임패드 CLI 옵션이 연결되지 않는다.

```bash
cd /home/aidl/work/Vision_Tracker_Project
AI/.venv/bin/python -m pip install -r WEB/requirements-dev.txt
sudo systemctl restart vision-tracker-web.service
```

동일 Wi-Fi 기기에서 `http://<Jetson-WiFi-IP>:8000`으로 접속합니다. 구현 시 주소는 `192.168.0.118`이며 DHCP에 따라 바뀔 수 있습니다. `ip -br -4 address`로 확인할 수 있습니다.

부팅 서비스 최초 설치는 `bash AUTOSTART/install.sh`. Uvicorn worker와 카메라 소유자는 하나만 사용합니다. 부팅 시 AI 카메라를 자동 시작하며 팬틸트 추적은 기본 OFF입니다. PyQt와 모니터는 필요 없습니다.

## 모드와 기능

- `AI + JPEG 영상`: YuNet·SFace 상태·팬틸트 추적·박스 표시
- `JPEG 영상 (AI 끔)`: 추론 없는 전송 성능 비교
- `카메라만`: AI·JPEG·전송 없는 카메라 기준 FPS
- 모드 변경은 카메라 OFF 후 ON
- 다시보기는 최근 60초 JPEG 버퍼, 실시간 복귀 시 최신 프레임부터 수신
- PNG 저장은 현재 표시 화면을 접속 기기에 다운로드
- 수동 방향 명령은 아직 서버 수신·기록만 수행하며 차량을 움직이지 않음

실시간 화면에서 `30초 수신 측정`을 누르고, 같은 장면과 Wi-Fi 거리에서 AI 유무를 비교합니다. 급격히 움직인 뒤 `프레임 나이`가 누적되지 않는지, `AI 건너뜀`이 늘어난 뒤 현재 장면으로 바로 따라오는지 확인합니다.

실제 카메라의 정적인 장면 검증에서는 640×480에서 캡처 30.0 FPS, AI 약 30 FPS, 처리 23.9ms, 프레임 나이 24.2ms가 측정됐습니다. 급격한 환경 변화와 Wi-Fi 결과는 접속 기기에서 다시 확인해야 합니다.

## 테스트

```bash
cd /home/aidl/work/Vision_Tracker_Project/WEB
../AI/.venv/bin/python -m unittest discover -s tests -v
cd ../AI
.venv/bin/python -m unittest discover -s tests -v
```
