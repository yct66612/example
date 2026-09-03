"""Development-only round-robin proxy used when Docker and Nginx are unavailable."""

import os
from collections.abc import Sequence
from contextlib import asynccontextmanager
from threading import Lock

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class RoundRobinPool:
    def __init__(self, upstreams: Sequence[str]) -> None:
        if not upstreams:
            raise ValueError("at least one upstream is required")
        self._upstreams = [upstream.rstrip("/") for upstream in upstreams]
        self._index = 0
        self._lock = Lock()

    def next(self) -> str:
        with self._lock:
            upstream = self._upstreams[self._index]
            self._index = (self._index + 1) % len(self._upstreams)
            return upstream


def create_proxy_app(upstreams: Sequence[str]) -> FastAPI:
    pool = RoundRobinPool(upstreams)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = httpx.AsyncClient(timeout=30)
        try:
            yield
        finally:
            await app.state.client.aclose()

    proxy_app = FastAPI(title="本地轮询负载均衡器", lifespan=lifespan)

    @proxy_app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def proxy(path: str, request: Request) -> Response:
        upstream = pool.next()
        target_url = f"{upstream}/{path}"
        request_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "host"
        }
        try:
            upstream_response = await request.app.state.client.request(
                request.method,
                target_url,
                params=request.query_params,
                content=await request.body(),
                headers=request_headers,
            )
        except httpx.RequestError as exc:
            return JSONResponse(
                status_code=502,
                content={"detail": f"upstream unavailable: {exc.request.url}"},
                headers={"X-Load-Balancer": "local-round-robin"},
            )

        response_headers = {
            name: value
            for name, value in upstream_response.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS
        }
        response_headers["X-Load-Balancer"] = "local-round-robin"
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    return proxy_app


configured_upstreams = os.getenv(
    "UPSTREAMS",
    "http://127.0.0.1:8101,http://127.0.0.1:8102,http://127.0.0.1:8103",
)
app = create_proxy_app(
    [upstream.strip() for upstream in configured_upstreams.split(",") if upstream.strip()]
)
