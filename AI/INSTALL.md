# AI 설치 및 실행

현재 실행 구성은 YOLO 사람 검출 TensorRT 엔진, BoT-SORT 단기 추적,
OSNet x0.25 TensorRT 엔진 기반 장기 ReID입니다. ONNX·PyTorch 폴백과 얼굴
검출 모델은 사용하지 않습니다.

필수 모델:

```text
AI/models/yolo11n-person.engine
AI/models/osnet_x0_25.engine
```

Jetson에서 사용하는 가상환경에 의존성을 설치합니다.

```bash
cd /home/aidl/work/Vision_Tracker_Project/AI
/home/aidl/work/venv/bin/python -m pip install -r requirements.txt
```

통합 웹·카메라·게임패드·UART 서비스 설치와 실행은 다음 문서를 참고합니다.

- 웹 사용법: [WEB/README.md](../WEB/README.md)
- 부팅 자동 실행: [AUTOSTART/README.md](../AUTOSTART/README.md)
- UART 프로토콜: [UART_PROTOCOL.md](UART_PROTOCOL.md)
- 장치 문제 해결: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

모델 파일이 없거나 현재 Jetson/TensorRT 버전과 맞지 않으면 AI 카메라 시작이
명확한 오류로 실패합니다. 다른 형식의 모델로 자동 전환하지 않습니다.
