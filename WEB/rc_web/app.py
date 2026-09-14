"""Jetson 카메라 추적과 게임패드 상태 웹 화면."""

import logging
import os
from contextlib import asynccontextmanager
from rc_web.vision import VisionService
from rc_web.vision_api import router_for
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(control_service=None) -> FastAPI:
    # JPEG 폴링은 초당 수십 건의 요청을 만들기 때문에 접근 로그를 끈다.
    # 오류 및 애플리케이션 로그는 uvicorn.error에 계속 기록된다.
    logging.getLogger("uvicorn.access").disabled = True
    vision = VisionService(control_service)

    @asynccontextmanager
    async def lifespan(app):
        if control_service is not None:
            control_service.start()
        try:
            if os.environ.get("VISION_AUTOSTART_CAMERA", "").lower() in {"1", "true", "yes", "on"}:
                try:
                    vision.start()
                except Exception as error:
                    vision.update(error=str(error))
            yield
        finally:
            try:
                vision.stop()
            finally:
                if control_service is not None:
                    control_service.stop()

    application = FastAPI(
        title="Jetson Vision Tracker",
        version="2.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.vision = vision
    application.state.control_service = control_service
    application.include_router(router_for(vision))
    @application.middleware("http")
    async def prevent_stale_status(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/", include_in_schema=False)
    def controller():
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/health")
    def health():
        return {"status": "ok", "control_enabled": control_service is not None}

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
