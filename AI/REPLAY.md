# 최근 프레임 다시보기

## 동작

실시간 처리 결과를 JPEG로 압축해 최근 60초만 메모리에 보관.

```text
영상 처리 프레임
→ 최신 프레임 전용 압축 Worker
→ JPEG 순환 버퍼
→ 시간 슬라이더 다시보기
```

슬라이더를 왼쪽으로 이동하면 해당 시점과 가장 가까운 프레임 표시. 다시보기 중에도 카메라, AI 처리, UART 전송과 버퍼 저장은 계속 실행. `실시간 복귀` 선택 시 최신 화면 표시.

실시간과 다시보기 화면 모두 `현재 화면 캡처` 버튼으로 PNG 저장 가능.

## 저장 방식

- 메모리 저장만 사용
- 프로그램 재시작 시 프레임 삭제
- 새 카메라 세션 시작 시 이전 버퍼 삭제
- 압축 대기 프레임이 쌓이면 오래된 대기 프레임 폐기
- 기본 JPEG 품질 `80`
- 기본 보관 시간 `60초`

보관 시간과 JPEG 품질은 `src/config.py`의 `REPLAY_BUFFER_SECONDS`, `REPLAY_JPEG_QUALITY`에서 변경 가능.

## 코드 위치

- `src/buffer/frame_buffer.py`: 시간 기준 JPEG 순환 버퍼
- `src/buffer/frame_buffer_worker.py`: 백그라운드 JPEG 압축과 복원
- `src/ui/main_window.py`: 시간 슬라이더와 실시간 복귀 처리
