> 웹 이식 이후 실행·화면·FPS 측정은 [WEB/README.md](../WEB/README.md)를 따릅니다. 아래 문서의 Qt/GUI 관련 설명은 이전 구현 기록입니다.

# unittest 테스트 가이드

게임패드·차량·서보 공통 프로토콜의 하드웨어 없는 테스트:
`python -m unittest tests.test_vehicle_control tests.test_gamepad_device tests.test_uart_protocol -v`.
`test_vehicle_control`은 호스트 GCC로 실제 STM32 공통 스트리밍 파서와 차량 C
코드를 임시 공유 라이브러리로 컴파일한다. 서보 패킷이 차량 watchdog을
갱신하지 않는 것과 카메라 종료가 차량 상태를 정지시키지 않는 것도 검증한다.
GCC가 없으면 해당 C 테스트만 skip된다. 세부 범위는 [GAMEPAD.md](GAMEPAD.md)와
[UART_PROTOCOL.md](UART_PROTOCOL.md)를 참고한다.

## PA0/PA1 서보 PWM 단독 진단

통합 실행과 UART를 제외하고 TIM2 PWM만 검사하는 별도 펌웨어를 제공한다. 두
서보가 90도에서 시작해 70도와 110도 사이를 1.5초마다 반복 이동한다. 차량 PWM은
진단 중 비활성 상태로 유지된다.

```bash
cd ~/work/Vision_Tracker_Project/STM32
make servo-test-run
```

진단 후에는 통합 펌웨어를 다시 플래시한다.

```bash
make run
```

## 가장 자주 사용하는 명령

`AI/` 디렉터리에서 아래 명령 하나로 모든 테스트 실행 가능.

```bash
cd ~/work/Vision_Tracker_Project/AI
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

`discover`가 `tests/` 안의 `test_*.py` 파일을 자동 검색하므로 테스트 파일을 하나씩 실행할 필요 없음.

옵션 의미:

- `-m unittest`: Python 기본 테스트 도구 실행
- `discover`: 테스트 파일 자동 검색
- `-s tests`: 검색 시작 폴더를 `tests/`로 지정
- `-v`: 각 테스트 이름과 결과를 자세히 표시

## 현재 테스트 구성

```text
tests/
├── test_camera_capture.py
├── test_yunet_detector.py
├── test_sface_extractor.py
├── test_face_tracker.py
├── test_uart_protocol.py
├── test_video_worker.py
├── test_frame_buffer.py
└── test_frame_capture.py
```

| 파일 | 확인 내용 |
|---|---|
| `test_camera_capture.py` | 기본 카메라 설정, 오류 처리, 안전한 해제, 실제 장치 연결 |
| `test_yunet_detector.py` | 모델 누락 오류, 검출 결과 변환, 얼굴 박스 표시 |
| `test_sface_extractor.py` | 모델 누락 오류, 128차원 벡터 추출, 잘못된 차원 검사 |
| `test_face_tracker.py` | 추적 대상 선택, 중심 무동작 영역, 각도 변경과 제한 |
| `test_uart_protocol.py` | 6바이트 패킷, 체크섬, PAN/TILT 연속 전송 |
| `test_video_worker.py` | 추적 기본 비활성화, 추적 시작·정지 전환 |
| `test_frame_buffer.py` | 프레임 추가, 시간 제한 제거, 시점 탐색, 초기화 |
| `test_frame_capture.py` | 실시간·다시보기 PNG 저장, 입력값과 폴더 검사 |

## 결과 읽는 방법

정상 실행 예시:

```text
test_default_state (...) ... ok
test_detect_converts_opencv_output (...) ... ok
test_extract_returns_128d_memory_vector (...) ... ok

Ran 30 tests in 0.030s
OK (skipped=1)
```

결과 의미:

- `ok`: 테스트 통과
- `skipped`: 실행 조건이 맞지 않아 의도적으로 건너뜀
- `FAIL`: 예상값과 실제값이 다름
- `ERROR`: 테스트 도중 예외 발생
- 마지막 `OK`: 실행된 테스트 전체 통과

실패 시 출력되는 `Traceback`의 마지막 부분에서 실패한 파일, 줄 번호, 예상값 확인 가능.

## 기능별 실행

전체 테스트가 아닌 특정 기능만 빠르게 확인할 때 사용.

카메라 테스트:

```bash
python3 -m unittest tests.test_camera_capture -v
```

YuNet 테스트:

```bash
python3 -m unittest tests.test_yunet_detector -v
```

SFace 테스트:

```bash
python3 -m unittest tests.test_sface_extractor -v
```

얼굴 추적 테스트:

```bash
python3 -m unittest tests.test_face_tracker -v
```

UART 패킷 테스트:

```bash
python3 -m unittest tests.test_uart_protocol -v
```

UART 테스트는 가짜 직렬 포트를 사용하므로 STM32 연결 없이 실행 가능.

추적 시작·정지 테스트:

```bash
python3 -m unittest tests.test_video_worker -v
```

프레임 버퍼 테스트:

```bash
python3 -m unittest tests.test_frame_buffer -v
```

프레임 버퍼 테스트는 카메라와 GUI 없이 실행 가능.

화면 캡처 테스트:

```bash
python3 -m unittest tests.test_frame_capture -v
```

화면 캡처 테스트는 임시 폴더를 사용하고 종료 시 저장 파일 자동 삭제.

## 클래스 또는 테스트 하나만 실행

테스트 클래스 전체 실행:

```bash
python3 -m unittest tests.test_sface_extractor.SFaceExtractorTest -v
```

특정 테스트 하나만 실행:

```bash
python3 -m unittest \
  tests.test_sface_extractor.SFaceExtractorTest.test_extract_returns_128d_memory_vector \
  -v
```

명령 형식:

```text
python3 -m unittest 패키지.파일명.클래스명.메서드명 -v
```

## 실제 카메라 테스트

기본 테스트에서는 실제 카메라 테스트를 자동으로 건너뜀. 카메라가 연결된 환경에서 아래 명령으로 활성화 가능.

```bash
RUN_CAMERA_TESTS=1 python3 -m unittest tests.test_camera_capture -v
```

카메라 장치 확인:

```bash
ls -l /dev/video*
python3 -m src.camera.camera_checker
```

`/dev/video0`이 없으면 실제 카메라 테스트는 `skipped` 처리됨.

## 문법 검사

테스트와 별도로 전체 Python 파일의 문법 및 import 가능한 바이트코드 생성 여부 확인 가능.

```bash
python3 -m compileall -q main.py src tests
```

출력이 없으면 문법 검사 통과. 오류가 있으면 해당 파일과 줄 번호 출력.

## 기본 작업 순서

코드 수정 후:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q main.py src tests
```

커밋 전에도 같은 두 명령 실행 권장.

## 테스트 코드 기본 형태

```python
import unittest


class ExampleTest(unittest.TestCase):
    def test_expected_value(self):
        result = 1 + 1
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
```

작성 규칙:

- `unittest.TestCase`를 상속한 클래스 사용
- 테스트 메서드 이름을 `test_`로 시작
- `assertEqual`, `assertTrue`, `assertRaises` 등으로 결과 검증
- 외부 카메라나 실제 모델 동작을 대체할 때 Fake 또는 Mock 사용 가능

자주 사용하는 검증 함수:

| 함수 | 용도 |
|---|---|
| `assertEqual(a, b)` | 두 값이 같은지 확인 |
| `assertTrue(value)` | 값이 참인지 확인 |
| `assertFalse(value)` | 값이 거짓인지 확인 |
| `assertAlmostEqual(a, b)` | 실수값이 허용 오차 안에서 같은지 확인 |
| `assertRaises(Error)` | 지정한 예외가 발생하는지 확인 |
| `assertIsNone(value)` | 값이 `None`인지 확인 |
