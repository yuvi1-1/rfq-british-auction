import argparse
import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import realtime
from app.auction import engine, service
from app.clock import Clock, utcnow
from app.config import settings
from app.enums import ExtensionTrigger, UserRole
from app.errors import BusinessRuleError, ConflictError
from app.models import Rfq, User
from app.schemas import BidCreate, DemoAuctionCreate, RfqCreate

log = logging.getLogger(__name__)

CARRIERS = ("Maersk", "MSC", "CMA CGM", "Hapag-Lloyd", "ONE", "Evergreen", "COSCO", "HMM")
CENT = Decimal("0.01")

# not used by the bots, so you can bid against them as this supplier
HUMAN_SUPPLIER_EMAIL = "arjun@oceanicfreight.test"

SessionFactory = async_sessionmaker[AsyncSession]


def demo_rfq_payload(now: datetime, options: DemoAuctionCreate) -> RfqCreate:
    close = now + timedelta(minutes=options.duration_minutes)
    return RfqCreate(
        name="Live demo: 2 x 40' HC, Shanghai → Nhava Sheva",
        origin="Shanghai, CN (CNSHA)",
        destination="Nhava Sheva, IN (INNSA)",
        currency="USD",
        pickup_date=(now + timedelta(days=10)).date(),
        bid_start_at=now,
        bid_close_at=close,
        forced_close_at=close + timedelta(minutes=options.forced_close_after_minutes),
        trigger_window_minutes=options.trigger_window_minutes,
        extension_minutes=options.extension_minutes,
        extension_trigger=options.extension_trigger,
    )


def split_quote(rng: random.Random, total: Decimal, carrier: str, today: date) -> BidCreate:
    """Break a total into freight / origin / destination charges that add up exactly."""
    freight = (total * Decimal(str(rng.uniform(0.76, 0.84)))).quantize(CENT)
    origin = (total * Decimal(str(rng.uniform(0.07, 0.10)))).quantize(CENT)
    return BidCreate(
        carrier_name=carrier,
        freight_charges=freight,
        origin_charges=origin,
        destination_charges=total - freight - origin,
        transit_time_days=rng.randint(16, 30),
        quote_validity_date=today + timedelta(days=30),
    )


@dataclass
class Bot:
    supplier_id: UUID
    carrier: str
    floor: Decimal  # never bids below this total
    eagerness: float  # relative chance of being the next to bid


def make_bots(suppliers: list[User], rng: random.Random, base: Decimal) -> list[Bot]:
    return [
        Bot(
            supplier_id=supplier.id,
            carrier=rng.choice(CARRIERS),
            floor=(base * Decimal(str(rng.uniform(0.80, 0.92)))).quantize(Decimal("1")),
            eagerness=rng.uniform(0.35, 0.9),
        )
        for supplier in suppliers
    ]


def next_move(
    rng: random.Random,
    bots: list[Bot],
    ranking: list[engine.RankedSupplier],
    base: Decimal,
    *,
    in_window: bool,
) -> tuple[Bot, Decimal] | None:
    """Pick which bot bids next and at what total, or None if nobody can improve."""
    by_supplier = {entry.supplier_id: entry for entry in ranking}
    l1_total = ranking[0].best_bid.total if ranking else None
    step = (0.005, 0.015) if in_window else (0.003, 0.010)
    candidates: list[tuple[Bot, Decimal]] = []
    for bot in bots:
        mine = by_supplier.get(bot.supplier_id)
        if mine is not None and mine.rank == 1:
            continue  # the leader waits to be challenged
        if mine is None:
            target = base * Decimal(str(rng.uniform(1.0, 1.10)))
        else:
            reference = (
                l1_total if l1_total is not None and rng.random() < 0.75 else mine.best_bid.total
            )
            target = min(reference * Decimal(str(1 - rng.uniform(*step))), mine.best_bid.total - 1)
        target = max(target, bot.floor).quantize(CENT)
        if mine is not None and target >= mine.best_bid.total:
            continue  # already at its floor
        candidates.append((bot, target))
    if not candidates:
        return None
    return rng.choices(candidates, weights=[bot.eagerness for bot, _ in candidates])[0]


async def _state(
    factory: SessionFactory, rfq_id: UUID
) -> tuple[Rfq | None, list[engine.RankedSupplier]]:
    async with factory() as session:
        rfq = await session.get(Rfq, rfq_id)
        if rfq is None:
            return None, []
        return rfq, engine.rank_suppliers(await service.load_snapshots(session, rfq_id))


async def run_bots(
    factory: SessionFactory,
    rfq_id: UUID,
    *,
    publisher: realtime.EventPublisher,
    seed: int | None = None,
    clock: Clock = utcnow,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """Keep bidding until the auction closes. Returns the number of bids placed."""
    rng = random.Random(seed)
    async with factory() as session:
        suppliers = list(
            (
                await session.scalars(
                    select(User)
                    .where(User.role == UserRole.SUPPLIER, User.email != HUMAN_SUPPLIER_EMAIL)
                    .order_by(User.email)
                )
            ).all()
        )
    if not suppliers:
        log.warning("No supplier accounts to run bots with; run `python -m app.seed` first")
        return 0

    base = Decimal(rng.randrange(2600, 3600, 25))
    bots = make_bots(suppliers, rng, base)
    placed = 0
    while True:
        rfq, _ = await _state(factory, rfq_id)
        now = clock()
        if rfq is None or now >= rfq.current_close_at:
            break
        if now < rfq.bid_start_at:
            await sleep(min((rfq.bid_start_at - now).total_seconds(), 5.0))
            continue

        remaining = (rfq.current_close_at - now).total_seconds()
        in_window = remaining <= rfq.trigger_window_minutes * 60
        pause = rng.uniform(2.0, 5.0) if in_window else rng.uniform(5.0, 10.0)
        await sleep(min(pause, max(remaining - 0.5, 0.25)))
        if not in_window and rng.random() < 0.35:
            continue  # quieter before the trigger window opens

        rfq, ranking = await _state(factory, rfq_id)
        if rfq is None or clock() >= rfq.current_close_at:
            break
        move = next_move(rng, bots, ranking, base, in_window=in_window)
        if move is None:
            continue
        bot, total = move
        async with factory() as session:
            supplier = await session.get(User, bot.supplier_id)
            if supplier is None:
                continue
            try:
                placement = await service.place_bid(
                    session,
                    rfq_id,
                    supplier,
                    split_quote(rng, total, bot.carrier, clock().date()),
                    clock=clock,
                )
            except ConflictError:
                break  # closed while we were deciding
            except BusinessRuleError:
                continue
        await publisher.publish(realtime.bid_update(placement))
        placed += 1

    log.info("Bidding bots finished on %s after %d bids", rfq_id, placed)
    return placed


async def run_bots_standalone(rfq_id: UUID, *, seed: int | None = None) -> int:
    """Run the bots with their own DB engine and Redis client (used by the Celery task)."""
    db_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        factory = async_sessionmaker(db_engine, expire_on_commit=False)
        return await run_bots(factory, rfq_id, publisher=realtime.RedisPublisher(redis), seed=seed)
    finally:
        await redis.aclose()
        await db_engine.dispose()


async def _cli(args: argparse.Namespace) -> None:
    db_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    publisher = realtime.RedisPublisher(redis)
    try:
        factory = async_sessionmaker(db_engine, expire_on_commit=False)
        options = DemoAuctionCreate(
            extension_trigger=ExtensionTrigger(args.trigger),
            duration_minutes=args.minutes,
            trigger_window_minutes=args.window,
            extension_minutes=args.extension,
            forced_close_after_minutes=args.forced_after,
        )
        async with factory() as session:
            buyer = await session.scalar(select(User).where(User.role == UserRole.BUYER).limit(1))
            if buyer is None:
                raise SystemExit("No buyer account found; run `python -m app.seed` first")
            now = utcnow()
            rfq = await service.create_rfq(session, buyer, demo_rfq_payload(now, options), now=now)
        await publisher.publish(realtime.rfq_update("rfq_created", rfq))
        print(f"Demo auction {rfq.reference_id} is live: http://localhost:5173/rfqs/{rfq.id}")
        placed = await run_bots(factory, rfq.id, publisher=publisher, seed=args.seed)
        print(f"Bidding finished: the bots placed {placed} bids.")
    finally:
        await redis.aclose()
        await db_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a short demo auction with bidding bots.")
    parser.add_argument("--minutes", type=int, default=3, help="bid close = now + minutes")
    parser.add_argument("--window", type=int, default=2, help="trigger window X (minutes)")
    parser.add_argument("--extension", type=int, default=1, help="extension Y (minutes)")
    parser.add_argument("--forced-after", type=int, default=4, help="forced close = bid close + N")
    parser.add_argument(
        "--trigger",
        choices=[t.value for t in ExtensionTrigger],
        default=ExtensionTrigger.L1_RANK_CHANGE.value,
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed for repeatable runs")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
