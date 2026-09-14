#!/usr/bin/env bash
set -euo pipefail

SOURCE_PROFILE="KCCI501"
TARGET_PROFILE="KCCI501_5G"
TARGET_SSID="KCCI501_5G"
TARGET_BSSID="B0:38:6C:4E:6A:02"

if ! nmcli -t -f NAME connection show | grep -Fxq "${TARGET_PROFILE}"; then
    nmcli connection clone "${SOURCE_PROFILE}" "${TARGET_PROFILE}"
fi

nmcli connection modify "${TARGET_PROFILE}" \
    connection.id "${TARGET_PROFILE}" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    802-11-wireless.ssid "${TARGET_SSID}" \
    802-11-wireless.band a \
    802-11-wireless.bssid "${TARGET_BSSID}"

nmcli connection modify "${SOURCE_PROFILE}" connection.autoconnect-priority 0
nmcli connection up "${TARGET_PROFILE}"

iw dev wlP1p1s0 link
