import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint

from app.api import demo, health, metrics, rfqs, users, ws
from app.clock import utcnow
from app.config import settings
from app.db import engine
from app.errors import DomainError, FieldError
from app.realtime import ConnectionManager, RedisPublisher, relay_redis_to_websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.publisher = RedisPublisher(redis)
    app.state.ws_manager = ConnectionManager()
    relay = asyncio.create_task(relay_redis_to_websockets(settings.redis_url, app.state.ws_manager))
    try:
        yield
    finally:
        relay.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    summary="RFQs with British (reverse) auction bidding, automatic extensions and forced close.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Server-Time"],
)


@app.middleware("http")
async def add_server_time(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Clients use this to correct their countdowns for a skewed local clock."""
    response = await call_next(request)
    response.headers["X-Server-Time"] = utcnow().isoformat()
    return response


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    if isinstance(exc, FieldError):
        detail = [{"loc": ["body", exc.field], "msg": exc.message, "type": "value_error"}]
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for router in (health.router, users.router, rfqs.router, metrics.router, demo.router, ws.router):
    app.include_router(router)
