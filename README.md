# Vision Tracker Project

AI 기반 객체 인식 및 STM32 임베디드 제어 시스템을 결합한 비전 트래킹 프로젝트.

게임패드 기반 차량 제어의 실행·핀맵·패킷·안전 정책·테스트는 [AI/GAMEPAD.md](AI/GAMEPAD.md)를 참고하세요. 기본 실행은 dry-run이며 실제 UART는 `--uart`로 명시해야 합니다.

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
