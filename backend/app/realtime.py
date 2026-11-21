import asyncio
import json
import logging
from typing import Any, Protocol

from fastapi import WebSocket
from redis.asyncio import Redis

from app.auction.service import BidPlacement, iso
from app.models import Rfq

log = logging.getLogger(__name__)

CHANNEL = "rfq:events"


class EventPublisher(Protocol):
    async def publish(self, message: dict[str, Any]) -> None: ...


class NullPublisher:
    async def publish(self, message: dict[str, Any]) -> None:
        return None


class RedisPublisher:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, message: dict[str, Any]) -> None:
        try:
            await self._redis.publish(CHANNEL, json.dumps(message, default=str))
        except Exception:
            log.warning(
                "Could not publish live update for %s", message.get("rfq_id"), exc_info=True
            )


def rfq_update(kind: str, rfq: Rfq, *, extension: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": kind,
        "rfq_id": str(rfq.id),
        "reference_id": rfq.reference_id,
        "name": rfq.name,
        "current_close_at": iso(rfq.current_close_at),
        "forced_close_at": iso(rfq.forced_close_at),
        "extension_count": rfq.extension_count,
        "extension": extension,
    }


def bid_update(placement: BidPlacement) -> dict[str, Any]:
    decision = placement.decision
    extension = None
    if decision.triggered:
        extension = {
            "extended": decision.extended,
            "capped": decision.capped,
            "old_close_at": iso(decision.old_close_at),
            "new_close_at": iso(decision.new_close_at),
            "trigger": placement.rfq.extension_trigger.value,
        }
    return rfq_update("bid_placed", placement.rfq, extension=extension)


class ConnectionManager:
    """WebSocket clients connected to this API instance, optionally filtered to one RFQ."""

    def __init__(self) -> None:
        self._clients: dict[WebSocket, str | None] = {}

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket, rfq_id: str | None) -> None:
        await websocket.accept()
        self._clients[websocket] = rfq_id

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.pop(websocket, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        target = message.get("rfq_id")
        recipients = [
            ws for ws, only in list(self._clients.items()) if only is None or only == target
        ]
        results = await asyncio.gather(
            *(ws.send_json(message) for ws in recipients), return_exceptions=True
        )
        for ws, result in zip(recipients, results, strict=True):
            if isinstance(result, Exception):
                self.disconnect(ws)


async def relay_redis_to_websockets(redis_url: str, manager: ConnectionManager) -> None:
    """Relay the Redis channel to this instance's WebSocket clients; reconnect on errors."""
    backoff = 1.0
    while True:
        client = Redis.from_url(redis_url, decode_responses=True)
        try:
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(CHANNEL)
                log.info("Live updates: subscribed to Redis channel %s", CHANNEL)
                backoff = 1.0
                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        await manager.broadcast(json.loads(message["data"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("Live updates: Redis unavailable, retrying in %.0fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            await client.aclose()
