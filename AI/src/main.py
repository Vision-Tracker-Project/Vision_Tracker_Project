"""통합 웹 애플리케이션 진입점."""

import os
import sys


def camera_autostart_enabled(environment=None) -> bool:
    values = os.environ if environment is None else environment
    return values.get("VISION_AUTOSTART_CAMERA", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main() -> int:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "WEB"))
    import uvicorn
    uvicorn.run(
        "rc_web.app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        proxy_headers=False,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
