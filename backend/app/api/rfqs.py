from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app import realtime
from app.api.deps import ClockDep, CurrentUser, PublisherDep, SessionDep
from app.auction import messages, queries, service
from app.enums import AuctionStatus, EventType
from app.schemas import AwardCreate, BidCreate, BidPlacedOut, RfqCreate, RfqDetail, RfqSummary

router = APIRouter(prefix="/api/rfqs", tags=["rfqs"])


@router.get("", response_model=list[RfqSummary], summary="Auction listing")
async def list_rfqs(
    session: SessionDep,
    user: CurrentUser,
    clock: ClockDep,
    status: AuctionStatus | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Search name, ID or lane")] = None,
) -> list[RfqSummary]:
    return await queries.list_rfqs(session, user, clock(), status=status, search=q)


@router.post("", response_model=RfqDetail, status_code=201, summary="Create an RFQ (buyers)")
async def create_rfq(
    data: RfqCreate,
    session: SessionDep,
    user: CurrentUser,
    clock: ClockDep,
    publisher: PublisherDep,
) -> RfqDetail:
    rfq = await service.create_rfq(session, user, data, now=clock())
    await publisher.publish(realtime.rfq_update("rfq_created", rfq))
    return await queries.get_rfq_detail(session, rfq.id, user, clock())


@router.get("/{rfq_id}", response_model=RfqDetail, summary="Auction details (role-aware)")
async def get_rfq(
    rfq_id: UUID, session: SessionDep, user: CurrentUser, clock: ClockDep
) -> RfqDetail:
    return await queries.get_rfq_detail(session, rfq_id, user, clock())


@router.post(
    "/{rfq_id}/bids",
    response_model=BidPlacedOut,
    status_code=201,
    summary="Submit a quote (suppliers)",
)
async def place_bid(
    rfq_id: UUID,
    data: BidCreate,
    session: SessionDep,
    user: CurrentUser,
    clock: ClockDep,
    publisher: PublisherDep,
) -> BidPlacedOut:
    placement = await service.place_bid(session, rfq_id, user, data, clock=clock)
    await publisher.publish(realtime.bid_update(placement))

    decision = placement.decision
    text = messages.render(EventType.BID_PLACED, placement.bid_event.details, str(user.id))
    if decision.extended:
        added = messages.duration_text(
            (decision.new_close_at - decision.old_close_at).total_seconds()
        )
        suffix = " (cut short at the forced close time)" if decision.capped else ""
        text += f" Your bid extended the auction by {added}{suffix}."
    elif decision.triggered:
        text += " No extension: the auction is at its forced close time."

    return BidPlacedOut(
        bid=queries.bid_out(placement.bid, is_best=True),
        rank=placement.rank,
        total_suppliers=placement.total_suppliers,
        extended=decision.extended,
        current_close_at=placement.rfq.current_close_at,
        message=text,
    )


@router.post("/{rfq_id}/award", response_model=RfqDetail, summary="Award a closed RFQ (buyers)")
async def award_rfq(
    rfq_id: UUID,
    data: AwardCreate,
    session: SessionDep,
    user: CurrentUser,
    clock: ClockDep,
    publisher: PublisherDep,
) -> RfqDetail:
    rfq, _ = await service.award_rfq(session, rfq_id, user, data.bid_id, now=clock())
    await publisher.publish(realtime.rfq_update("auction_awarded", rfq))
    return await queries.get_rfq_detail(session, rfq_id, user, clock())
