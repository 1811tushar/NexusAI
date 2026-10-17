"""X-Internal-API-Key on every /internal/* route (AI-FD-01, SEC-02): constant-time compare, no key in logs."""
from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException

from app.api.schemas import ErrorCode
from app.core.config import Settings, get_settings


class ApiError(HTTPException):
    def __init__(self, status: int, code: ErrorCode, message: str, retryable: bool = False,
                 details: dict[str, str] | None = None) -> None:
        super().__init__(status_code=status, detail=message)
        self.code, self.message, self.retryable, self.details = code, message, retryable, details


def require_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    supplied = (x_internal_api_key or "").encode("utf-8")
    expected = settings.internal_api_key.encode("utf-8")
    # compare_digest on every request (also when the header is missing) so timing does not reveal presence/length matches
    if not hmac.compare_digest(supplied, expected) or not supplied:
        raise ApiError(401, ErrorCode.UNAUTHENTICATED, "Missing or invalid internal API key")
