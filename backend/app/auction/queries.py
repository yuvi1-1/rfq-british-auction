from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auction import engine, messages
from app.enums import AuctionStatus, EventType, UserRole
from app.errors import NotFoundError
from app.models import AuctionEvent, Bid, Rfq, User
from app.schemas import (
    AuctionConfigOut,
    AuctionMetricsRow,
    AwardOut,
    BidOut,
    CohortStats,
    EventOut,
    MetricsOut,
    MetricsSummary,
    RankingEntryOut,
    RfqDetail,
    RfqSummary,
    SupplierPositionOut,
)


def status_of(rfq: Rfq, now: datetime) -> AuctionStatus:
    return engine.derive_status(
        now,
        bid_start_at=rfq.bid_start_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
    )


def status_filter(status: AuctionStatus, now: datetime) -> ColumnElement[bool]:
    """SQL equivalent of engine.derive_status (kept in sync by tests/test_api_rfqs.py)."""
    match status:
        case AuctionStatus.UPCOMING:
            return Rfq.bid_start_at > now
        case AuctionStatus.ACTIVE:
            return and_(Rfq.bid_start_at <= now, Rfq.current_close_at > now)
        case AuctionStatus.CLOSED:
            return and_(Rfq.current_close_at <= now, Rfq.current_close_at < Rfq.forced_close_at)
        case AuctionStatus.FORCE_CLOSED:
            return and_(Rfq.current_close_at <= now, Rfq.current_close_at >= Rfq.forced_close_at)
    raise ValueError(f"Unknown status: {status}")


def to_summary(
    rfq: Rfq,
    now: datetime,
    *,
    lowest_bid: Decimal | None,
    bid_count: int,
    supplier_count: int,
    my_rank: int | None = None,
) -> RfqSummary:
    return RfqSummary(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        origin=rfq.origin,
        destination=rfq.destination,
        currency=rfq.currency,
        pickup_date=rfq.pickup_date,
        bid_start_at=rfq.bid_start_at,
        bid_close_at=rfq.bid_close_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        status=status_of(rfq, now),
        config=AuctionConfigOut(
            trigger_window_minutes=rfq.trigger_window_minutes,
            extension_minutes=rfq.extension_minutes,
            extension_trigger=rfq.extension_trigger,
        ),
        lowest_bid=lowest_bid,
        bid_count=bid_count,
        supplier_count=supplier_count,
        extension_count=rfq.extension_count,
        is_awarded=rfq.awarded_bid_id is not None,
        my_rank=my_rank,
    )


def bid_out(bid: Bid, *, is_best: bool) -> BidOut:
    return BidOut(
        id=bid.id,
        supplier_id=bid.supplier_id,
        supplier_name=bid.supplier.company,
        carrier_name=bid.carrier_name,
        freight_charges=bid.freight_charges,
        origin_charges=bid.origin_charges,
        destination_charges=bid.destination_charges,
        total_amount=bid.total_amount,
        transit_time_days=bid.transit_time_days,
        quote_validity_date=bid.quote_validity_date,
        created_at=bid.created_at,
        is_best=is_best,
    )


def _listing_order(item: RfqSummary) -> tuple[int, float]:
    # active first, then upcoming, then most recently closed
    match item.status:
        case AuctionStatus.ACTIVE:
            return (0, item.current_close_at.timestamp())
        case AuctionStatus.UPCOMING:
            return (1, item.bid_start_at.timestamp())
        case _:
            return (2, -item.current_close_at.timestamp())


async def list_rfqs(
    session: AsyncSession,
    viewer: User,
    now: datetime,
    *,
    status: AuctionStatus | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[RfqSummary]:
    stmt = select(Rfq)
    if status is not None:
        stmt = stmt.where(status_filter(status, now))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Rfq.name.ilike(pattern),
                Rfq.reference_id.ilike(pattern),
                Rfq.origin.ilike(pattern),
                Rfq.destination.ilike(pattern),
            )
        )
    rfqs = (await session.scalars(stmt.order_by(Rfq.current_close_at.desc()).limit(limit))).all()
    if not rfqs:
        return []

    ids = [rfq.id for rfq in rfqs]
    stats_rows = await session.execute(
        select(
            Bid.rfq_id,
            func.min(Bid.total_amount),
            func.count(Bid.id),
            func.count(distinct(Bid.supplier_id)),
        )
        .where(Bid.rfq_id.in_(ids))
        .group_by(Bid.rfq_id)
    )
    stats = {row[0]: (row[1], row[2], row[3]) for row in stats_rows}
    my_ranks = (
        await _supplier_ranks(session, ids, viewer.id) if viewer.role == UserRole.SUPPLIER else {}
    )

    items = []
    for rfq in rfqs:
        lowest, bid_count, supplier_count = stats.get(rfq.id, (None, 0, 0))
        items.append(
            to_summary(
                rfq,
                now,
                lowest_bid=lowest,
                bid_count=bid_count,
                supplier_count=supplier_count,
                my_rank=my_ranks.get(rfq.id),
            )
        )
    return sorted(items, key=_listing_order)


async def _supplier_ranks(
    session: AsyncSession, rfq_ids: list[UUID], supplier_id: UUID
) -> dict[UUID, int]:
    """The viewing supplier's current rank in each RFQ they have bid on."""
    participated = select(Bid.rfq_id).where(Bid.supplier_id == supplier_id)
    rows = await session.execute(
        select(Bid.rfq_id, Bid.id, Bid.supplier_id, Bid.total_amount, Bid.created_at).where(
            Bid.rfq_id.in_(rfq_ids), Bid.rfq_id.in_(participated)
        )
    )
    by_rfq: dict[UUID, list[engine.BidSnapshot]] = defaultdict(list)
    for row in rows:
        by_rfq[row.rfq_id].append(
            engine.BidSnapshot(row.id, row.supplier_id, row.total_amount, row.created_at)
        )
    ranks: dict[UUID, int] = {}
    for rfq_id, snapshots in by_rfq.items():
        rank = engine.rank_map(engine.rank_suppliers(snapshots)).get(supplier_id)
        if rank is not None:
            ranks[rfq_id] = rank
    return ranks


def _actor_for_supplier(event: AuctionEvent, viewer: User) -> str | None:
    if event.actor is None:
        return None
    if event.actor.id == viewer.id:
        return "You"
    if event.actor.role == UserRole.BUYER:
        return event.actor.company
    return None  # competitors stay anonymous


async def get_rfq_detail(
    session: AsyncSession, rfq_id: UUID, viewer: User, now: datetime
) -> RfqDetail:
    rfq = await session.get(Rfq, rfq_id, populate_existing=True)
    if rfq is None:
        raise NotFoundError("RFQ not found")

    bids = (
        await session.scalars(
            select(Bid)
            .where(Bid.rfq_id == rfq.id)
            .order_by(Bid.total_amount, Bid.created_at, Bid.id)
        )
    ).all()
    ranking = engine.rank_suppliers(
        engine.BidSnapshot(b.id, b.supplier_id, b.total_amount, b.created_at) for b in bids
    )
    by_id = {bid.id: bid for bid in bids}
    best_ids = {entry.best_bid.bid_id for entry in ranking}
    bids_per_supplier = Counter(bid.supplier_id for bid in bids)
    events = (
        await session.scalars(
            select(AuctionEvent)
            .where(AuctionEvent.rfq_id == rfq.id)
            .order_by(AuctionEvent.occurred_at.desc(), AuctionEvent.id.desc())
            .limit(500)
        )
    ).all()
    buyer = await session.get(User, rfq.buyer_id)
    status = status_of(rfq, now)
    lowest = ranking[0].best_bid.total if ranking else None
    awarded_bid = by_id.get(rfq.awarded_bid_id) if rfq.awarded_bid_id else None
    summary = to_summary(
        rfq, now, lowest_bid=lowest, bid_count=len(bids), supplier_count=len(ranking)
    )

    if viewer.role == UserRole.BUYER:
        ranking_out = [
            RankingEntryOut(
                rank=entry.rank,
                supplier_id=entry.supplier_id,
                supplier_name=by_id[entry.best_bid.bid_id].supplier.company,
                bid_count=bids_per_supplier[entry.supplier_id],
                bid=bid_out(by_id[entry.best_bid.bid_id], is_best=True),
            )
            for entry in ranking
        ]
        bids_out = [bid_out(bid, is_best=bid.id in best_ids) for bid in bids]
        position = None
        events_out = [
            EventOut(
                id=event.id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                actor_name=event.actor.company if event.actor else None,
                message=event.message,
                details=event.details,
            )
            for event in events
        ]
        award = (
            AwardOut(
                awarded_at=rfq.awarded_at,
                bid_id=awarded_bid.id,
                supplier_name=awarded_bid.supplier.company,
                carrier_name=awarded_bid.carrier_name,
                total_amount=awarded_bid.total_amount,
            )
            if awarded_bid and rfq.awarded_at
            else None
        )
    else:
        viewer_key = str(viewer.id)
        mine = next((entry for entry in ranking if entry.supplier_id == viewer.id), None)
        ranking_out = []
        bids_out = [
            bid_out(bid, is_best=bid.id in best_ids) for bid in bids if bid.supplier_id == viewer.id
        ]
        position = SupplierPositionOut(
            rank=mine.rank if mine else None,
            total_suppliers=len(ranking),
            best_bid=bid_out(by_id[mine.best_bid.bid_id], is_best=True) if mine else None,
            l1_total=lowest,
            gap_to_l1=(mine.best_bid.total - lowest) if mine and lowest is not None else None,
            is_l1=bool(mine and mine.rank == 1),
        )
        events_out = [
            EventOut(
                id=event.id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                actor_name=_actor_for_supplier(event, viewer),
                message=messages.render(event.event_type, event.details, viewer_key),
                details=messages.sanitize(event.event_type, event.details, viewer_key),
            )
            for event in events
        ]
        award = None
        if awarded_bid and rfq.awarded_at:
            won = awarded_bid.supplier_id == viewer.id
            award = AwardOut(
                awarded_at=rfq.awarded_at,
                awarded_to_me=won,
                bid_id=awarded_bid.id if won else None,
                supplier_name=awarded_bid.supplier.company if won else None,
                carrier_name=awarded_bid.carrier_name if won else None,
                total_amount=awarded_bid.total_amount if won else None,
            )

    is_owner = viewer.role == UserRole.BUYER and viewer.id == rfq.buyer_id
    return RfqDetail(
        **summary.model_dump(),
        viewer_role=viewer.role,
        buyer_company=buyer.company if buyer else "",
        ranking=ranking_out,
        bids=bids_out,
        my_position=position,
        events=events_out,
        award=award,
        can_bid=viewer.role == UserRole.SUPPLIER and status == AuctionStatus.ACTIVE,
        can_award=(
            is_owner
            and status in engine.ENDED_STATUSES
            and rfq.awarded_bid_id is None
            and bool(ranking)
        ),
    )


def _mean(values: list[float | int | None]) -> float | None:
    present = [float(v) for v in values if v is not None]
    return round(sum(present) / len(present), 2) if present else None


def _cohort(rows: list[AuctionMetricsRow]) -> CohortStats:
    return CohortStats(
        auctions=len(rows),
        avg_bids_per_rfq=_mean([r.bid_count for r in rows]),
        avg_suppliers_per_rfq=_mean([r.supplier_count for r in rows]),
        avg_price_improvement_pct=_mean([r.price_improvement_pct for r in rows]),
    )


async def compute_metrics(session: AsyncSession, now: datetime) -> MetricsOut:
    """Bids per RFQ and price improvement, comparing extended with non-extended auctions."""
    rfqs = (await session.scalars(select(Rfq))).all()
    bid_rows = await session.execute(
        select(Bid.rfq_id, Bid.supplier_id, Bid.total_amount, Bid.created_at).order_by(
            Bid.created_at, Bid.id
        )
    )
    bids_by_rfq: dict[UUID, list] = defaultdict(list)
    for row in bid_rows:
        bids_by_rfq[row.rfq_id].append(row)
    late_bids = await session.scalar(
        select(func.count())
        .select_from(AuctionEvent)
        .where(
            AuctionEvent.event_type == EventType.BID_PLACED,
            AuctionEvent.details["in_trigger_window"].as_boolean(),
        )
    )

    rows: list[AuctionMetricsRow] = []
    for rfq in rfqs:
        bids = bids_by_rfq.get(rfq.id, [])
        status = status_of(rfq, now)
        opening = bids[0].total_amount if bids else None
        final = min(b.total_amount for b in bids) if bids else None
        improvement = (
            round(float((opening - final) / opening * 100), 2) if opening and final else None
        )
        rows.append(
            AuctionMetricsRow(
                id=rfq.id,
                reference_id=rfq.reference_id,
                name=rfq.name,
                status=status,
                currency=rfq.currency,
                bid_count=len(bids),
                supplier_count=len({b.supplier_id for b in bids}),
                extension_count=rfq.extension_count,
                opening_price=opening,
                final_price=final,
                price_improvement_pct=improvement,
                ended_at=rfq.current_close_at if status in engine.ENDED_STATUSES else None,
            )
        )
    close_times = {rfq.id: rfq.current_close_at for rfq in rfqs}
    rows.sort(key=lambda r: close_times[r.id], reverse=True)

    started = [r for r in rows if r.status != AuctionStatus.UPCOMING]
    ended = [r for r in rows if r.status in engine.ENDED_STATUSES]
    ended_with_bids = [r for r in ended if r.bid_count > 0]
    total_bids = sum(r.bid_count for r in rows)

    summary = MetricsSummary(
        total_auctions=len(rows),
        upcoming_auctions=sum(r.status == AuctionStatus.UPCOMING for r in rows),
        active_auctions=sum(r.status == AuctionStatus.ACTIVE for r in rows),
        ended_auctions=len(ended),
        total_bids=total_bids,
        total_extensions=sum(r.extension_count for r in rows),
        avg_bids_per_rfq=_mean([r.bid_count for r in started]),
        avg_suppliers_per_rfq=_mean([r.supplier_count for r in started]),
        avg_price_improvement_pct=_mean([r.price_improvement_pct for r in ended_with_bids]),
        extended_share_pct=(
            round(sum(r.extension_count > 0 for r in ended) / len(ended) * 100, 2)
            if ended
            else None
        ),
        late_bid_share_pct=round((late_bids or 0) / total_bids * 100, 2) if total_bids else None,
    )
    return MetricsOut(
        summary=summary,
        extended=_cohort([r for r in ended_with_bids if r.extension_count > 0]),
        not_extended=_cohort([r for r in ended_with_bids if r.extension_count == 0]),
        auctions=rows,
    )
