"""iPhone → Jetson 명령 수신 검증 API 및 동일 출처 웹 화면."""

import logging
import os
from contextlib import asynccontextmanager
from rc_web.vision import VisionService
from rc_web.vision_api import router_for
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rc_web.commands import CommandReceipt, CommandRequest, CommandStore, handle_command


STATIC_DIR = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("uvicorn.error")


def create_app(history_capacity: int = 100, control_service=None) -> FastAPI:
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
    store = CommandStore(history_capacity)
    application.state.command_store = store

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
        return {"status": "ok", "mode": "receive_only", "hardware_enabled": False}

    @application.post("/api/command", response_model=CommandReceipt)
    def receive_command(payload: CommandRequest, request: Request):
        client_ip = request.client.host if request.client else None
        receipt = handle_command(payload, store, client_ip)
        logger.info(
            "RC RX #%d command=%s action=%s received_at=%s client_ip=%s hardware_sent=false",
            receipt.sequence, receipt.command.value, receipt.action,
            receipt.received_at.isoformat(), receipt.client_ip,
        )
        return receipt

    @application.get("/api/status")
    def status():
        # 최근 명령과 기록을 한 잠금에서 읽어 화면의 시점 불일치 방지.
        return {**health(), **store.snapshot()}

    @application.get("/api/history")
    def history():
        snapshot = store.snapshot()
        return {
            "instance_id": snapshot["instance_id"],
            "total_received": snapshot["total_received"],
            "capacity": snapshot["history_capacity"],
            "count": len(snapshot["history"]),
            "history": snapshot["history"],
        }

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
