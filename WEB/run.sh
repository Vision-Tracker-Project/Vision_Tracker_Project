#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WEB_PYTHON="${WEB_PYTHON:-${WEB_DIR}/../AI/.venv/bin/python}"
if [[ ! -x "$WEB_PYTHON" ]]; then
    echo "AI/.venv가 없습니다. WEB/README.md의 설치 명령을 먼저 실행하세요." >&2
    exit 1
fi
cd "$WEB_DIR"
# 메모리 기록을 공유할 수 있도록 단일 Worker 사용. 프록시 헤더로 IP를 덮어쓰지 않음.
exec "$WEB_PYTHON" -m uvicorn rc_web.app:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers
