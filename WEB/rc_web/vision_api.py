import logging
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict


class StartRequest(BaseModel):
    mode: Literal['camera', 'raw', 'ai'] = 'ai'


class TrackingRequest(BaseModel):
    enabled: bool


class TargetRequest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ClientReport(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    session: str = Field(max_length=64)
    seconds: float = Field(gt=0, le=3600)
    displayed: int = Field(ge=0, le=1000000)
    skipped: int = Field(ge=0, le=1000000)
    fps: float = Field(ge=0, le=1000)
    request_ms: float = Field(ge=0, le=60000)


def router_for(service):
    router = APIRouter(prefix='/api/vision')

    @router.get('/status')
    def status():
        return service.status()

    @router.post('/start')
    def start(payload: StartRequest):
        try:
            service.start(payload.mode)
        except Exception as error:
            raise HTTPException(409, str(error)) from error
        return service.status()

    @router.post('/stop')
    def stop():
        try:
            service.stop()
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        return service.status()

    @router.post('/tracking')
    def tracking(payload: TrackingRequest):
        try:
            service.track(payload.enabled)
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        return service.status()

    @router.post('/target')
    def target(payload: TargetRequest):
        try:
            selected_id = service.select_target(payload.x, payload.y)
        except (RuntimeError, ValueError) as error:
            raise HTTPException(409, str(error)) from error
        return {'selected_id': selected_id, **service.status()}

    @router.post('/target/clear')
    def clear_target():
        try:
            service.clear_target()
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        return service.status()

    @router.get('/frame')
    def frame(after: int = Query(0, ge=0)):
        item = service.frame(after)
        if not item:
            return Response(status_code=204)
        sequence, timestamp, data = item
        return Response(data, media_type='image/jpeg', headers={
            'X-Sequence': str(sequence), 'X-Session': service.session,
            'X-Frame-Time': str(timestamp)})

    @router.post('/report')
    def report(payload: ClientReport, request: Request):
        record = {**payload.model_dump(), 'client_ip': request.client.host if request.client else None}
        with service.condition:
            service.reports.append(record)
        logging.getLogger('uvicorn.error').info('VIDEO CLIENT %s', record)
        return {'ok': True}

    return router
