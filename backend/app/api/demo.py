import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app import realtime, simulator
from app.api.deps import ClockDep, CurrentUser, PublisherDep, SessionDep
from app.auction import queries, service
from app.config import settings
from app.errors import ConflictError
from app.schemas import DemoAuctionCreate, DemoAuctionOut

log = logging.getLogger(__name__)
router = APIRouter(tags=["demo"])

BotLauncher = Callable[[UUID], Awaitable[bool]]


async def enqueue_bidding_bots(rfq_id: UUID) -> bool:
    """Hand the bot run to a Celery worker; the API request returns immediately."""
    from app.worker import run_bidding_bots

    try:
        await asyncio.to_thread(run_bidding_bots.apply_async, args=[str(rfq_id)], retry=False)
    except Exception:
        log.warning("Could not enqueue bidding bots (is the Celery broker up?)", exc_info=True)
        return False
    return True


def get_bot_launcher() -> BotLauncher:
    return enqueue_bidding_bots


@router.post(
    "/api/demo/auctions",
    response_model=DemoAuctionOut,
    status_code=201,
    summary="Start a short live auction with bidding bots (buyers)",
)
async def launch_demo_auction(
    data: DemoAuctionCreate,
    session: SessionDep,
    user: CurrentUser,
    clock: ClockDep,
    publisher: PublisherDep,
    launch_bots: Annotated[BotLauncher, Depends(get_bot_launcher)],
) -> DemoAuctionOut:
    if not settings.demo_enabled:
        raise ConflictError("Demo mode is turned off on this server")
    now = clock()
    rfq = await service.create_rfq(session, user, simulator.demo_rfq_payload(now, data), now=now)
    await publisher.publish(realtime.rfq_update("rfq_created", rfq))
    started = await launch_bots(rfq.id)
    summary = queries.to_summary(rfq, now, lowest_bid=None, bid_count=0, supplier_count=0)
    return DemoAuctionOut(rfq=summary, bots_started=started)
