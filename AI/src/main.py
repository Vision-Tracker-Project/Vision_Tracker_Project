"""PyQt 애플리케이션 진입점."""

import os
import sys


def main() -> int:
    try:
        from PyQt5.QtCore import QLibraryInfo
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print(
            "PyQt5가 설치되어 있지 않습니다. README의 설치 방법을 확인하세요.",
            file=sys.stderr,
        )
        return 1

    from src.ui.main_window import MainWindow

    # pip의 opencv-python은 import될 때 자체 Qt 플러그인 경로를 환경 변수에
    # 기록한다. 시스템 PyQt5와 섞이면 xcb 플러그인을 로드하지 못하므로,
    # QApplication 생성 직전에 현재 PyQt5의 플러그인 경로로 복원한다.
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
        QLibraryInfo.PluginsPath
    )
    os.environ.pop("QT_QPA_FONTDIR", None)

    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
