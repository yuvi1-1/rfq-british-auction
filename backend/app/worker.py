import asyncio
import logging
from uuid import UUID

from celery import Celery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import realtime, simulator
from app.auction import service
from app.clock import utcnow
from app.config import settings

log = logging.getLogger(__name__)

celery_app = Celery("rfq_auction", broker=settings.redis_url)
celery_app.conf.update(
    task_ignore_result=True,
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "close-due-auctions": {
            "task": "auctions.close_due",
            "schedule": settings.close_sweep_interval_seconds,
            "options": {"expires": max(settings.close_sweep_interval_seconds * 5, 10.0)},
        },
    },
)


@celery_app.task(name="auctions.close_due")
def close_due_auctions() -> int:
    """Finalize auctions whose close time has passed, log the close event and notify clients."""
    return asyncio.run(_close_due_auctions())


async def _close_due_auctions() -> int:
    db_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        factory = async_sessionmaker(db_engine, expire_on_commit=False)
        async with factory() as session:
            closed = await service.close_due_auctions(session, now=utcnow())
        publisher = realtime.RedisPublisher(redis)
        for item in closed:
            await publisher.publish(realtime.rfq_update("auction_closed", item.rfq))
            log.info("%s: %s", item.rfq.reference_id, item.event.message)
        return len(closed)
    finally:
        await redis.aclose()
        await db_engine.dispose()


@celery_app.task(name="demo.run_bidding_bots", acks_late=False, soft_time_limit=3600)
def run_bidding_bots(rfq_id: str, seed: int | None = None) -> int:
    """Long-running demo job: bots keep bidding until the auction closes."""
    return asyncio.run(simulator.run_bots_standalone(UUID(rfq_id), seed=seed))
