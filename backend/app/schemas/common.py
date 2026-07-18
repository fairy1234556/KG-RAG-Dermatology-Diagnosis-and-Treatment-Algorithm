from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


class ApiResponse(BaseModel):
    request_id: str = Field(default_factory=new_request_id)
    success: bool = True
    message: str = "ok"
    data: Any = None


class ErrorDetail(BaseModel):
    error_code: str
    detail: str


class ErrorResponse(BaseModel):
    request_id: str = Field(default_factory=new_request_id)
    success: bool = False
    message: str
    data: Optional[ErrorDetail] = None


class AppError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 400) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def ok(data: Any = None, message: str = "ok") -> ApiResponse:
    return ApiResponse(success=True, message=message, data=data)

