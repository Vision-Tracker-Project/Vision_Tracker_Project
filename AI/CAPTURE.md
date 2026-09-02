# 화면 캡처

## 동작

`현재 화면 캡처` 선택 시 영상 영역에 표시 중인 프레임을 PNG로 저장.

- 실시간 화면: 파일명 끝에 `_live.png` 사용
- 다시보기 화면: 파일명 끝에 `_replay.png` 사용
- 저장 성공: 영상 테두리를 0.25초 동안 노란색으로 표시
- 단축키: 미사용

기본 저장 위치는 `AI/captures/`. 저장 파일은 Git 추적에서 제외.

## 저장 폴더 변경

`저장 폴더 선택` 버튼으로 기존 폴더 지정 가능. 선택한 경로는 프로그램 실행 중 유지.

## 파일명

```text
capture_YYYYMMDD_HHMMSS_microseconds_live.png
capture_YYYYMMDD_HHMMSS_microseconds_replay.png
```

## 코드 위치

- `src/capture/frame_capture.py`: PNG 저장과 파일명 생성
- `src/ui/main_window.py`: 캡처·폴더 선택 버튼과 테두리 표시
- `src/config.py`: 기본 폴더와 테두리 표시 시간
