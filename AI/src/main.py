"""PC PyQt 애플리케이션 단일 진입점."""

import os
import sys


def main() -> int:
    try:
        from PyQt5.QtCore import QLibraryInfo
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print(
            "PyQt5가 설치되어 있지 않습니다. INSTALL.md의 설치 방법을 확인하세요.",
            file=sys.stderr,
        )
        return 1

    from src.config import (
        DISCOVERY_INTERVAL_SECONDS,
        DISCOVERY_PORT,
        METADATA_PORT,
        VIDEO_PORT,
    )
    from src.network.discovery import PcDiscoveryBroadcaster
    from src.ui.network_main_window import MainWindow

    # pip OpenCV가 Qt 플러그인 경로를 바꾸는 경우 시스템 PyQt5 경로로 복원한다.
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
        QLibraryInfo.PluginsPath
    )
    os.environ.pop("QT_QPA_FONTDIR", None)

    advertiser = PcDiscoveryBroadcaster(
        DISCOVERY_PORT,
        VIDEO_PORT,
        METADATA_PORT,
        DISCOVERY_INTERVAL_SECONDS,
    )
    advertiser.start()
    print(f"PC 자동 탐색 송신 시작: UDP {DISCOVERY_PORT}")

    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    try:
        return application.exec_()
    finally:
        advertiser.stop()


if __name__ == "__main__":
    raise SystemExit(main())
