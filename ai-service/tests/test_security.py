"""API-key enforcement without a database (tiny app that mounts the same dependency)."""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.security import ApiError, require_api_key
from tests.conftest import API_KEY


def _app():
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def h(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"code": exc.code.value, "message": exc.message}, status_code=exc.status_code)

    @app.get("/internal/x", dependencies=[Depends(require_api_key)])
    def x():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}
    return app


def test_missing_wrong_and_right_key():
    c = TestClient(_app())
    assert c.get("/health").status_code == 200
    assert c.get("/internal/x").status_code == 401
    assert c.get("/internal/x", headers={"X-Internal-API-Key": "nope"}).status_code == 401
    assert c.get("/internal/x", headers={"X-Internal-API-Key": ""}).status_code == 401
    assert c.get("/internal/x", headers={"X-Internal-API-Key": API_KEY + "x"}).status_code == 401
    r = c.get("/internal/x", headers={"X-Internal-API-Key": API_KEY})
    assert r.status_code == 200


def test_uses_constant_time_compare():
    import inspect
    assert "compare_digest" in inspect.getsource(require_api_key)
