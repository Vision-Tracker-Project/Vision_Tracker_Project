# 테스트

AI 단위 테스트와 문법 검사는 실제 카메라 없이 실행할 수 있습니다.

```bash
cd /home/aidl/work/Vision_Tracker_Project/AI
/home/aidl/work/venv/bin/python -m unittest discover -s tests -v
/home/aidl/work/venv/bin/python -m compileall -q main.py src tests
```

주요 테스트 범위는 카메라, 프레임 캡처, YOLO 결과 변환/NMS, OSNet 특징과
갤러리, 사람 선택·ReID·팬틸트 추적, 게임패드 안전 상태, UART 패킷 및 통합
제어입니다. `test_vehicle_control`은 호스트 GCC가 있으면 STM32 공통 C 코드를
임시 공유 라이브러리로 빌드해 파서와 차량 watchdog도 검사합니다.

실제 카메라까지 검사하려면 다음처럼 명시적으로 활성화합니다.

```bash
RUN_CAMERA_TESTS=1 /home/aidl/work/venv/bin/python -m unittest tests.test_camera_capture -v
```

TIM2 팬·틸트 PWM 단독 진단은 STM32 디렉터리에서 실행합니다.

```bash
cd /home/aidl/work/Vision_Tracker_Project/STM32
make servo-test-run
```

진단 후에는 `make run`으로 통합 펌웨어를 다시 플래시합니다.
