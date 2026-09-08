#!/usr/bin/env bash
set -euo pipefail
AUTOSTART_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${AUTOSTART_DIR}/.." && pwd)"
SERVICE_USER="$(id -un)"
SERVICE_GROUP="$(id -gn)"
USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
USER_AUTOSTART_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
"${PROJECT_ROOT}/AI/.venv/bin/python" -c "import cv2, serial, fastapi, uvicorn"
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
    "${AUTOSTART_DIR}/systemd/vision-tracker-web.service.in" > "$rendered_web_unit"
sudo install -m 0644 "$rendered_web_unit" /etc/systemd/system/vision-tracker-web.service
sudo systemctl daemon-reload
sudo systemctl enable vision-tracker-web.service
sudo systemctl restart vision-tracker-web.service
printf '%s\n' '통합 웹 서버 활성화: vision-tracker-web.service (8000)'
