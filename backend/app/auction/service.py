import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auction import engine, messages
from app.clock import Clock, utcnow
from app.enums import EventType, UserRole
from app.errors import (
    BusinessRuleError,
    ConflictError,
    FieldError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models import AuctionEvent, Bid, Rfq, User
from app.schemas import BidCreate, RfqCreate


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def amount(value: Decimal) -> str:
    return f"{value:.2f}"


def new_event(
    rfq: Rfq,
    event_type: EventType,
    occurred_at: datetime,
    details: dict[str, Any],
    *,
    actor: User | None = None,
    bid: Bid | None = None,
) -> AuctionEvent:
    return AuctionEvent(
        rfq_id=rfq.id,
        event_type=event_type,
        actor=actor,
        bid_id=bid.id if bid else None,
        message=messages.render(event_type, details),
        details=details,
        occurred_at=occurred_at,
    )


async def load_snapshots(session: AsyncSession, rfq_id: uuid.UUID) -> list[engine.BidSnapshot]:
    rows = await session.execute(
        select(Bid.id, Bid.supplier_id, Bid.total_amount, Bid.created_at).where(
            Bid.rfq_id == rfq_id
        )
    )
    return [engine.BidSnapshot(r.id, r.supplier_id, r.total_amount, r.created_at) for r in rows]


async def supplier_names(
    session: AsyncSession, supplier_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, str]:
    ids = set(supplier_ids)
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.company).where(User.id.in_(ids)))
    return {row.id: row.company for row in rows}


async def _lock_rfq(session: AsyncSession, rfq_id: uuid.UUID) -> Rfq:
    # row lock: bids on the same auction are processed one at a time
    rfq = await session.scalar(
        select(Rfq)
        .where(Rfq.id == rfq_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if rfq is None:
        raise NotFoundError("RFQ not found")
    return rfq


async def _generate_reference_id(session: AsyncSession, now: datetime) -> str:
    while True:
        number = await session.scalar(text("SELECT nextval('rfq_reference_seq')"))
        candidate = f"RFQ-{now.year}-{number:04d}"
        taken = await session.scalar(select(exists().where(Rfq.reference_id == candidate)))
        if not taken:
            return candidate


async def create_rfq(
    session: AsyncSession,
    buyer: User,
    data: RfqCreate,
    *,
    now: datetime,
    enforce_future: bool = True,
    commit: bool = True,
) -> Rfq:
    """Create an RFQ with British auction rules."""
    if buyer.role != UserRole.BUYER:
        raise PermissionDeniedError("Only buyers can create RFQs")
    if enforce_future:
        if data.bid_close_at <= now:
            raise FieldError("bid_close_at", "Bid close time must be in the future")
        if data.pickup_date < (now - timedelta(days=1)).date():
            raise FieldError("pickup_date", "Pickup / service date cannot be in the past")

    if data.reference_id:
        taken = await session.scalar(select(exists().where(Rfq.reference_id == data.reference_id)))
        if taken:
            raise FieldError("reference_id", f"Reference ID {data.reference_id} is already in use")
        reference_id = data.reference_id
    else:
        reference_id = await _generate_reference_id(session, now)

    rfq = Rfq(
        id=uuid.uuid7(),
        reference_id=reference_id,
        name=data.name,
        buyer_id=buyer.id,
        origin=data.origin,
        destination=data.destination,
        currency=data.currency,
        pickup_date=data.pickup_date,
        bid_start_at=data.bid_start_at,
        bid_close_at=data.bid_close_at,
        current_close_at=data.bid_close_at,
        forced_close_at=data.forced_close_at,
        trigger_window_minutes=data.trigger_window_minutes,
        extension_minutes=data.extension_minutes,
        extension_trigger=data.extension_trigger,
        extension_count=0,
    )
    session.add(rfq)
    await session.flush()
    session.add(
        new_event(
            rfq,
            EventType.RFQ_CREATED,
            now,
            {
                "trigger": data.extension_trigger.value,
                "trigger_window_minutes": data.trigger_window_minutes,
                "extension_minutes": data.extension_minutes,
                "bid_start_at": iso(data.bid_start_at),
                "bid_close_at": iso(data.bid_close_at),
                "forced_close_at": iso(data.forced_close_at),
            },
            actor=buyer,
        )
    )
    try:
        await (session.commit() if commit else session.flush())
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("That reference ID is already in use") from exc
    return rfq


@dataclass(frozen=True, slots=True)
class BidPlacement:
    rfq: Rfq
    bid: Bid
    rank: int
    total_suppliers: int
    decision: engine.ExtensionDecision
    bid_event: AuctionEvent
    extension_event: AuctionEvent | None


async def place_bid(
    session: AsyncSession,
    rfq_id: uuid.UUID,
    supplier: User,
    data: BidCreate,
    *,
    clock: Clock = utcnow,
    commit: bool = True,
) -> BidPlacement:
    """Accept a supplier's quote and apply the British auction extension rules atomically."""
    if supplier.role != UserRole.SUPPLIER:
        raise PermissionDeniedError("Only suppliers can submit quotes")

    rfq = await _lock_rfq(session, rfq_id)
    # read the time after getting the lock
    now = clock()
    if now < rfq.bid_start_at:
        raise ConflictError("Bidding has not started yet for this RFQ")
    if rfq.closed_at is not None or now >= rfq.current_close_at:
        raise ConflictError("Bidding is closed for this RFQ")
    if data.quote_validity_date < now.date():
        raise FieldError("quote_validity_date", "Quote validity date cannot be in the past")

    snapshots = await load_snapshots(session, rfq.id)
    before = engine.rank_suppliers(snapshots)
    own = next((entry for entry in before if entry.supplier_id == supplier.id), None)
    total = data.total
    if own is not None and total >= own.best_bid.total:
        raise BusinessRuleError(
            f"Your new total ({messages.money(rfq.currency, total)}) must be lower than "
            f"your current best ({messages.money(rfq.currency, own.best_bid.total)})"
        )

    bid = Bid(
        id=uuid.uuid7(),
        rfq_id=rfq.id,
        supplier=supplier,
        carrier_name=data.carrier_name,
        freight_charges=data.freight_charges,
        origin_charges=data.origin_charges,
        destination_charges=data.destination_charges,
        transit_time_days=data.transit_time_days,
        quote_validity_date=data.quote_validity_date,
        created_at=now,
    )
    session.add(bid)
    await session.flush()

    after = engine.rank_suppliers([*snapshots, engine.BidSnapshot(bid.id, supplier.id, total, now)])
    old_ranks, new_ranks = engine.rank_map(before), engine.rank_map(after)
    decision = engine.decide_extension(
        trigger=rfq.extension_trigger,
        window_minutes=rfq.trigger_window_minutes,
        extension_minutes=rfq.extension_minutes,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        now=now,
        before=before,
        after=after,
    )

    l1_before, l1_after = engine.l1_supplier(before), engine.l1_supplier(after)
    bid_event = new_event(
        rfq,
        EventType.BID_PLACED,
        now,
        {
            "supplier_id": str(supplier.id),
            "supplier_name": supplier.company,
            "carrier_name": bid.carrier_name,
            "total": amount(total),
            "currency": rfq.currency,
            "rank": new_ranks[supplier.id],
            "previous_rank": old_ranks.get(supplier.id),
            "became_l1": l1_after == supplier.id and l1_before != supplier.id,
            "in_trigger_window": decision.in_window,
        },
        actor=supplier,
        bid=bid,
    )
    session.add(bid_event)

    extension_event = None
    if decision.triggered:
        names = await supplier_names(session, new_ranks)

        def party(supplier_id: uuid.UUID | None) -> dict[str, str] | None:
            if supplier_id is None:
                return None
            return {"supplier_id": str(supplier_id), "supplier_name": names[supplier_id]}

        details = {
            "trigger": rfq.extension_trigger.value,
            "trigger_window_minutes": rfq.trigger_window_minutes,
            "extension_minutes": rfq.extension_minutes,
            "old_close_at": iso(decision.old_close_at),
            "new_close_at": iso(decision.new_close_at),
            "forced_close_at": iso(rfq.forced_close_at),
            "capped": decision.capped,
            "added_seconds": (decision.new_close_at - decision.old_close_at).total_seconds(),
            "supplier_id": str(supplier.id),
            "supplier_name": supplier.company,
            "rank_changes": [
                {
                    "supplier_id": str(change.supplier_id),
                    "supplier_name": names[change.supplier_id],
                    "old_rank": change.old_rank,
                    "new_rank": change.new_rank,
                }
                for change in engine.rank_changes(before, after)
            ],
            "previous_l1": party(l1_before),
            "new_l1": party(l1_after),
        }
        if decision.extended:
            rfq.current_close_at = decision.new_close_at
            rfq.extension_count += 1
            extension_event = new_event(
                rfq, EventType.AUCTION_EXTENDED, now, details, actor=supplier, bid=bid
            )
        else:
            extension_event = new_event(
                rfq, EventType.EXTENSION_CAPPED, now, details, actor=supplier, bid=bid
            )
        session.add(extension_event)

    await (session.commit() if commit else session.flush())
    return BidPlacement(
        rfq=rfq,
        bid=bid,
        rank=new_ranks[supplier.id],
        total_suppliers=len(after),
        decision=decision,
        bid_event=bid_event,
        extension_event=extension_event,
    )


@dataclass(frozen=True, slots=True)
class ClosedAuction:
    rfq: Rfq
    event: AuctionEvent


async def close_due_auctions(
    session: AsyncSession, *, now: datetime, limit: int = 100
) -> list[ClosedAuction]:
    """Finalize auctions whose close time has passed and log why they ended."""
    due = (
        await session.scalars(
            select(Rfq)
            .where(Rfq.closed_at.is_(None), Rfq.current_close_at <= now)
            .order_by(Rfq.current_close_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
    ).all()

    closed: list[ClosedAuction] = []
    for rfq in due:
        snapshots = await load_snapshots(session, rfq.id)
        ranking = engine.rank_suppliers(snapshots)
        names = await supplier_names(session, (entry.supplier_id for entry in ranking))
        forced = rfq.current_close_at >= rfq.forced_close_at
        l1 = ranking[0] if ranking else None
        details = {
            "closed_at": iso(rfq.current_close_at),
            "forced": forced,
            "currency": rfq.currency,
            "bid_count": len(snapshots),
            "supplier_count": len(ranking),
            "extension_count": rfq.extension_count,
            "l1": (
                {
                    "supplier_id": str(l1.supplier_id),
                    "supplier_name": names[l1.supplier_id],
                    "total": amount(l1.best_bid.total),
                }
                if l1
                else None
            ),
            "final_ranks": {str(entry.supplier_id): entry.rank for entry in ranking},
        }
        rfq.closed_at = now
        event_type = EventType.AUCTION_FORCE_CLOSED if forced else EventType.AUCTION_CLOSED
        event = new_event(rfq, event_type, rfq.current_close_at, details)
        session.add(event)
        closed.append(ClosedAuction(rfq, event))

    await session.commit()
    return closed


async def award_rfq(
    session: AsyncSession, rfq_id: uuid.UUID, buyer: User, bid_id: uuid.UUID, *, now: datetime
) -> tuple[Rfq, AuctionEvent]:
    """The buyer picks the winning quote once bidding has ended (any supplier's final bid)."""
    if buyer.role != UserRole.BUYER:
        raise PermissionDeniedError("Only buyers can award RFQs")
    rfq = await _lock_rfq(session, rfq_id)
    if rfq.buyer_id != buyer.id:
        raise PermissionDeniedError("Only the buyer who created this RFQ can award it")
    status = engine.derive_status(
        now,
        bid_start_at=rfq.bid_start_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
    )
    if status not in engine.ENDED_STATUSES:
        raise ConflictError("An RFQ can only be awarded after its auction has closed")
    if rfq.awarded_bid_id is not None:
        raise ConflictError("This RFQ has already been awarded")

    ranking = engine.rank_suppliers(await load_snapshots(session, rfq.id))
    entry = next((e for e in ranking if e.best_bid.bid_id == bid_id), None)
    if entry is None:
        raise BusinessRuleError("Only a supplier's final (best) bid on this RFQ can be awarded")

    bid = await session.get(Bid, bid_id)
    assert bid is not None
    rfq.awarded_bid_id = bid.id
    rfq.awarded_at = now
    event = new_event(
        rfq,
        EventType.AUCTION_AWARDED,
        now,
        {
            "bid_id": str(bid.id),
            "supplier_id": str(bid.supplier_id),
            "supplier_name": bid.supplier.company,
            "carrier_name": bid.carrier_name,
            "total": amount(bid.total_amount),
            "currency": rfq.currency,
            "rank": entry.rank,
        },
        actor=buyer,
        bid=bid,
    )
    session.add(event)
    await session.commit()
    return rfq, event
