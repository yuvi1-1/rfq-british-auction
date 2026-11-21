from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.enums import AuctionStatus, ExtensionTrigger


@dataclass(frozen=True, slots=True)
class BidSnapshot:
    bid_id: UUID
    supplier_id: UUID
    total: Decimal
    placed_at: datetime


@dataclass(frozen=True, slots=True)
class RankedSupplier:
    rank: int  # 1 == L1 (lowest price)
    supplier_id: UUID
    best_bid: BidSnapshot


@dataclass(frozen=True, slots=True)
class RankChange:
    supplier_id: UUID
    old_rank: int | None  # None: the supplier is bidding for the first time
    new_rank: int


@dataclass(frozen=True, slots=True)
class ExtensionDecision:
    in_window: bool  # the bid landed inside the last X minutes before the current close
    triggered: bool  # ...and the configured trigger condition was met
    old_close_at: datetime
    new_close_at: datetime  # equals old_close_at when nothing was extended
    capped: bool  # the forced close time shortened (or blocked) the extension

    @property
    def extended(self) -> bool:
        return self.new_close_at > self.old_close_at


def _sort_key(bid: BidSnapshot) -> tuple[Decimal, datetime, UUID]:
    return (bid.total, bid.placed_at, bid.bid_id)


def rank_suppliers(bids: Iterable[BidSnapshot]) -> list[RankedSupplier]:
    """Rank suppliers by their best (lowest) total. On equal totals the earlier bid ranks higher."""
    best: dict[UUID, BidSnapshot] = {}
    for bid in bids:
        current = best.get(bid.supplier_id)
        if current is None or _sort_key(bid) < _sort_key(current):
            best[bid.supplier_id] = bid
    ordered = sorted(best.values(), key=_sort_key)
    return [
        RankedSupplier(rank=position, supplier_id=bid.supplier_id, best_bid=bid)
        for position, bid in enumerate(ordered, start=1)
    ]


def rank_map(ranking: Sequence[RankedSupplier]) -> dict[UUID, int]:
    return {entry.supplier_id: entry.rank for entry in ranking}


def l1_supplier(ranking: Sequence[RankedSupplier]) -> UUID | None:
    return ranking[0].supplier_id if ranking else None


def rank_changes(
    before: Sequence[RankedSupplier], after: Sequence[RankedSupplier]
) -> list[RankChange]:
    """Suppliers whose rank differs after a bid. A first-time bidder counts as a change."""
    old = rank_map(before)
    return [
        RankChange(entry.supplier_id, old.get(entry.supplier_id), entry.rank)
        for entry in after
        if old.get(entry.supplier_id) != entry.rank
    ]


def in_trigger_window(now: datetime, close_at: datetime, window_minutes: int) -> bool:
    """True when `now` falls inside the last X minutes before the current close time."""
    return close_at - timedelta(minutes=window_minutes) <= now < close_at


def is_triggered(
    trigger: ExtensionTrigger,
    before: Sequence[RankedSupplier],
    after: Sequence[RankedSupplier],
) -> bool:
    """Whether a bid that moved the ranking from `before` to `after` meets the trigger."""
    match trigger:
        case ExtensionTrigger.BID_RECEIVED:
            return True
        case ExtensionTrigger.ANY_RANK_CHANGE:
            return bool(rank_changes(before, after))
        case ExtensionTrigger.L1_RANK_CHANGE:
            return l1_supplier(before) != l1_supplier(after)
    raise ValueError(f"Unknown extension trigger: {trigger}")


def decide_extension(
    *,
    trigger: ExtensionTrigger,
    window_minutes: int,
    extension_minutes: int,
    current_close_at: datetime,
    forced_close_at: datetime,
    now: datetime,
    before: Sequence[RankedSupplier],
    after: Sequence[RankedSupplier],
) -> ExtensionDecision:
    """Apply the British auction rules to one accepted bid."""
    in_window = in_trigger_window(now, current_close_at, window_minutes)
    if not (in_window and is_triggered(trigger, before, after)):
        return ExtensionDecision(in_window, False, current_close_at, current_close_at, False)

    uncapped = current_close_at + timedelta(minutes=extension_minutes)
    new_close_at = min(uncapped, forced_close_at)
    return ExtensionDecision(
        in_window=True,
        triggered=True,
        old_close_at=current_close_at,
        new_close_at=new_close_at,
        capped=new_close_at < uncapped,
    )


def derive_status(
    now: datetime,
    *,
    bid_start_at: datetime,
    current_close_at: datetime,
    forced_close_at: datetime,
) -> AuctionStatus:
    """Status is always computed from the stored times, so it can never go stale."""
    if now < bid_start_at:
        return AuctionStatus.UPCOMING
    if now < current_close_at:
        return AuctionStatus.ACTIVE
    if current_close_at >= forced_close_at:
        return AuctionStatus.FORCE_CLOSED
    return AuctionStatus.CLOSED


ENDED_STATUSES = frozenset({AuctionStatus.CLOSED, AuctionStatus.FORCE_CLOSED})
