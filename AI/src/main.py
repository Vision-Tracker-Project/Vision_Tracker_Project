"""통합 웹 애플리케이션 진입점."""

import logging
import os
import sys
from pathlib import Path


def camera_autostart_enabled(environment=None) -> bool:
    values = os.environ if environment is None else environment
    return values.get("VISION_AUTOSTART_CAMERA", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "WEB"))

    import uvicorn

    from rc_web.app import create_app
    from src.control.__main__ import create_service

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    control_service = create_service()
    application = create_app(control_service=control_service)
    uvicorn.run(
        application,
        host="0.0.0.0",
        port=8000,
        workers=1,
        proxy_headers=False,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
