from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.schemas.common import AppError, ErrorDetail, ErrorResponse, new_request_id


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.system_version,
        description="Stage-1 backend for the dermatology KG-RAG assistant system.",
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        response = ErrorResponse(
            request_id=new_request_id(),
            success=False,
            message=exc.message,
            data=ErrorDetail(error_code=exc.error_code, detail=exc.message),
        )
        return JSONResponse(status_code=exc.status_code, content=response.model_dump())

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        response = ErrorResponse(
            request_id=new_request_id(),
            success=False,
            message="Unexpected backend error.",
            data=ErrorDetail(error_code="KG_LOAD_FAILED", detail=str(exc)),
        )
        return JSONResponse(status_code=500, content=response.model_dump())

    app.include_router(api_router)
    return app


app = create_app()
