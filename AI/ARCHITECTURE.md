# AI 모듈 구조

차량 제어는 `src/control/`의 독립 루프에서 실행합니다. `ControlService`가 UART를 단독 소유하고 영상 작업자는 `ServoMailbox`에 최신 서보 패킷을 제출합니다. 프레임 지연이 차량 입력 처리를 막지 않습니다. 실행·프로토콜·향후 서보 펌웨어 통합은 [GAMEPAD.md](GAMEPAD.md)를 참고하세요.

```text
AI/
├── main.py                   # 프로그램 실행 진입점
├── src/
│   ├── config.py             # 카메라, 모델, 추적, UART 설정
│   ├── main.py               # PyQt 애플리케이션 생성
│   ├── camera/               # USB 카메라 연결·조회·해제
│   ├── detection/            # YuNet 얼굴 검출
│   ├── recognition/          # SFace 특징 벡터 추출
│   ├── tracking/             # 추적 얼굴 선택과 팬·틸트 각도 계산
│   ├── communication/        # 6바이트 패킷 생성과 UART 전송
│   ├── workers/              # 카메라·AI·통신 백그라운드 처리
│   └── ui/                   # 영상과 처리 상태 표시
├── models/                   # YuNet·SFace ONNX 모델
└── tests/                    # 모듈별 unittest
```

## 데이터 흐름

```text
USB 카메라
→ YuNet 얼굴 검출
→ SFace 특징 벡터 추출
→ 추적 얼굴 선택
→ 중심 좌표 필터링
→ 팬·틸트 각도 계산
→ 패킷 생성
→ STM32 UART 전송
```

현재 얼굴 등록과 유사도 비교는 미구현. 추적 대상은 가장 큰 얼굴로 선택.
