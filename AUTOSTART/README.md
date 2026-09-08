# 통합 웹 서버 자동 실행

`bash AUTOSTART/install.sh`는 기존 사용자 GUI 서비스를 중지·비활성화하고 GUI 자동 시작 파일을 `.disabled`로 보관합니다. 이어 통합 시스템 웹 서비스를 설치·재시작합니다. sudo 인증을 먼저 확인하고, 검증용 `vision-tracker-preview.service`가 있으면 중지하여 카메라 중복 사용을 방지합니다.

- 서비스: `vision-tracker-web.service`, 포트 8000
- Python: `AI/.venv/bin/python` (OpenCV, pyserial, FastAPI, Uvicorn 필요)
- 부팅 시 AI 카메라 시작, 팬틸트 추적 기본 OFF
- 디스플레이·PyQt·그래픽 로그인 불필요
- 카메라·UART 접근을 위해 기존 `PrivateDevices=true`를 해제
- GDM 자동 로그인 설정은 변경하지 않음

```bash
systemctl status vision-tracker-web.service
journalctl -u vision-tracker-web.service -n 50 --no-pager
```

실행·Wi-Fi FPS 비교는 `../WEB/README.md` 참고.
