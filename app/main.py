import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings

app = FastAPI(title="任务调度看板")
app.include_router(router)
access_logger = logging.getLogger("uvicorn.error")


@app.middleware("http")
async def add_observability_headers(request: Request, call_next):
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started_at = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - started_at) * 1000
    response.headers["X-App-Instance"] = settings.app_instance
    response.headers["X-Request-ID"] = request_id
    access_logger.info(
        "instance=%s request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        settings.app_instance,
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "instance": get_settings().app_instance}

static_directory = Path(__file__).parent / "static"
if static_directory.exists():
    app.mount("/static", StaticFiles(directory=static_directory), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(static_directory / "index.html")
