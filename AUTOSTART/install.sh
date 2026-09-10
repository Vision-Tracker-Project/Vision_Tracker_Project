#!/usr/bin/env bash
set -euo pipefail
if [[ "$EUID" -eq 0 ]]; then
    echo "이 스크립트는 로그인 사용자로 실행하세요. 필요한 단계에서 sudo를 요청합니다." >&2
    exit 1
fi
AUTOSTART_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${AUTOSTART_DIR}/.." && pwd)"
SERVICE_USER="$(id -un)"
SERVICE_GROUP="$(id -gn)"
USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
USER_AUTOSTART_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
GAMEPAD_DEVICE="${VISION_GAMEPAD_DEVICE:-/dev/input/event6}"
UART_DEVICE="${VISION_UART_DEVICE:-/dev/ttyACM2}"
GAMEPAD_CONFIG="${VISION_GAMEPAD_CONFIG:-${PROJECT_ROOT}/AI/gamepad.local.json}"
PYTHON_BIN="${VISION_PYTHON:-}"

if [[ -n "$PYTHON_BIN" && ! -x "$PYTHON_BIN" ]]; then
    echo "VISION_PYTHON 실행 파일을 찾을 수 없습니다: $PYTHON_BIN" >&2
    exit 1
fi
if [[ -z "$PYTHON_BIN" ]]; then
    for candidate in \
        "${PROJECT_ROOT}/AI/.venv/bin/python" \
        "${PROJECT_ROOT}/AI/venv/bin/python"; do
        if [[ -x "$candidate" ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi
if [[ -z "$PYTHON_BIN" && -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
fi
if [[ -z "$PYTHON_BIN" ]]; then
    echo "Python 가상환경을 찾지 못했습니다." >&2
    echo "AI/.venv, AI/venv 또는 VISION_PYTHON=/절대경로/bin/python 중 하나가 필요합니다." >&2
    exit 1
fi
if [[ "$PYTHON_BIN" != /* ]]; then
    echo "Python 경로는 절대 경로여야 합니다: $PYTHON_BIN" >&2
    exit 1
fi

for value in "$PROJECT_ROOT" "$PYTHON_BIN" "$GAMEPAD_DEVICE" "$UART_DEVICE" "$GAMEPAD_CONFIG"; do
    if [[ "$value" == *'|'* || "$value" == *'%'* || "$value" =~ [[:space:]] ]]; then
        echo "설정 경로에 지원하지 않는 문자가 있습니다: $value" >&2
        exit 1
    fi
done
for required_group in input dialout; do
    if ! getent group "$required_group" >/dev/null; then
        echo "필수 시스템 그룹이 없습니다: $required_group" >&2
        exit 1
    fi
done
if [[ ! -r "$GAMEPAD_CONFIG" ]]; then
    echo "게임패드 설정을 읽을 수 없습니다: $GAMEPAD_CONFIG" >&2
    echo "AI/gamepad.example.json을 AI/gamepad.local.json으로 복사하고 측정한 버튼 코드를 입력하세요." >&2
    exit 1
fi
"$PYTHON_BIN" -c "import cv2, serial, evdev, fastapi, uvicorn"
"$PYTHON_BIN" - "$GAMEPAD_CONFIG" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    mapping = json.load(stream).get("buttons", {})
if (set(mapping) != {"enable", "stop", "slower", "faster"}
        or any(type(value) is not int or value < 0 for value in mapping.values())
        or len(set(mapping.values())) != 4):
    raise SystemExit("buttons에는 측정한 서로 다른 정수 코드 4개가 필요합니다.")
PY

if [[ "$GAMEPAD_DEVICE" == /dev/input/event* ]]; then
    echo "주의: $GAMEPAD_DEVICE 번호는 재부팅 후 바뀔 수 있습니다. /dev/input/by-id 경로를 권장합니다." >&2
fi
if [[ "$UART_DEVICE" == /dev/ttyACM* || "$UART_DEVICE" == /dev/ttyUSB* ]]; then
    echo "주의: $UART_DEVICE 번호는 재부팅 후 바뀔 수 있습니다. /dev/serial/by-id 경로를 권장합니다." >&2
fi
# Authenticate before changing the running services.
sudo -v
systemctl --user stop vision-tracker-preview.service 2>/dev/null || true
# Retire the desktop camera owner before starting the unified service.
systemctl --user disable --now vision-tracker-ai.service 2>/dev/null || true
if [[ -f "${USER_AUTOSTART_DIR}/vision-tracker-ai.desktop" ]]; then
    mv "${USER_AUTOSTART_DIR}/vision-tracker-ai.desktop" "${USER_AUTOSTART_DIR}/vision-tracker-ai.desktop.disabled"
fi
if [[ -f "${USER_SYSTEMD_DIR}/vision-tracker-ai.service" ]]; then
    mv "${USER_SYSTEMD_DIR}/vision-tracker-ai.service" "${USER_SYSTEMD_DIR}/vision-tracker-ai.service.disabled"
fi
systemctl --user daemon-reload
rendered_web_unit="$(mktemp)"
trap 'rm -f "$rendered_web_unit"' EXIT
sed -e "s|@PROJECT_ROOT@|${PROJECT_ROOT}|g" -e "s|@SERVICE_USER@|${SERVICE_USER}|g" \
    -e "s|@SERVICE_GROUP@|${SERVICE_GROUP}|g" \
    -e "s|@PYTHON_BIN@|${PYTHON_BIN}|g" \
    -e "s|@GAMEPAD_DEVICE@|${GAMEPAD_DEVICE}|g" \
    -e "s|@GAMEPAD_CONFIG@|${GAMEPAD_CONFIG}|g" \
    -e "s|@UART_DEVICE@|${UART_DEVICE}|g" \
    "${AUTOSTART_DIR}/systemd/vision-tracker-web.service.in" > "$rendered_web_unit"
sudo install -m 0644 "$rendered_web_unit" /etc/systemd/system/vision-tracker-web.service
sudo systemctl daemon-reload
sudo systemctl enable vision-tracker-web.service
sudo systemctl restart vision-tracker-web.service
printf '%s\n' \
    '통합 자동 실행 활성화: vision-tracker-web.service (웹 8000)' \
    "Python: ${PYTHON_BIN}" \
    "게임패드: ${GAMEPAD_DEVICE}" \
    "STM32 UART: ${UART_DEVICE}" \
    "버튼 설정: ${GAMEPAD_CONFIG}"
