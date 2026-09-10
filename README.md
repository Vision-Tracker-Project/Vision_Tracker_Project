# Vision Tracker Project

AI 기반 객체 인식 및 STM32 임베디드 제어 시스템을 결합한 비전 트래킹 프로젝트.

현재 UI는 PyQt를 제거한 통합 웹 화면입니다. 카메라·AI·다시보기·캡처를 Wi-Fi 브라우저에서 사용하고, 차량은 별도의 USB 게임패드로 제어합니다. [웹 실행 및 FPS 측정](WEB/README.md) · [게임패드 차량 제어](AI/GAMEPAD.md) · [통합 UART 프로토콜](AI/UART_PROTOCOL.md) · [부팅 자동 실행](AUTOSTART/README.md)

---

## 팀원

- 김경태
- 도재우
- 이세형
- 조성수

## 📁 프로젝트 구조

```text
Vision_Tracker_Project/
├── AI/                     # AI/컴퓨터 비전 모델 및 추론 코드
├── STM32/                  # STM32 펌웨어 소스코드 및 Makefile
├── .gitignore              # 빌드 산출물 및 임시 파일 제외 설정
└── README.md               # 프로젝트 안내 문서
```
