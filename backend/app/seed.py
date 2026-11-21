import argparse
import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auction import engine, service
from app.clock import utcnow
from app.config import settings
from app.enums import ExtensionTrigger, UserRole
from app.errors import BusinessRuleError, ConflictError
from app.models import Rfq, User
from app.schemas import RfqCreate
from app.simulator import CARRIERS, CENT, split_quote

BUYER = ("Priya Sharma", "Acme Retail Imports", "priya@acmeretail.test")
SUPPLIERS = [
    ("Arjun Mehta", "Oceanic Freight Co.", "arjun@oceanicfreight.test"),
    ("Sara Khan", "BlueWave Logistics", "sara@bluewave.test"),
    ("Daniel Ortiz", "TransGlobal Shipping", "daniel@transglobal.test"),
    ("Mei Lin", "Swift Cargo Lines", "mei@swiftcargo.test"),
    ("Omar Haddad", "Horizon Forwarders", "omar@horizonfwd.test"),
]

T = ExtensionTrigger


@dataclass(frozen=True)
class PastAuction:
    name: str
    origin: str
    destination: str
    days_ago: int
    trigger: ExtensionTrigger
    window: int  # X
    extension: int  # Y
    forced_after: int  # forced close = bid close + this many minutes
    late_rounds: int  # bids inside the trigger window; 0 means a quiet finish
    award_rank: int | None  # which final rank the buyer awarded, if any


PAST_AUCTIONS = [
    PastAuction(
        "FCL 40' HC: consumer electronics",
        "Shenzhen, CN (CNSZX)",
        "Rotterdam, NL (NLRTM)",
        days_ago=13,
        trigger=T.L1_RANK_CHANGE,
        window=10,
        extension=5,
        forced_after=30,
        late_rounds=3,
        award_rank=1,
    ),
    PastAuction(
        "FCL 20': ceramic tiles",
        "Mundra, IN (INMUN)",
        "New York, US (USNYC)",
        days_ago=11,
        trigger=T.BID_RECEIVED,
        window=10,
        extension=5,
        forced_after=15,
        late_rounds=5,
        award_rank=1,
    ),
    PastAuction(
        "LCL: machine spare parts",
        "Busan, KR (KRPUS)",
        "Los Angeles, US (USLAX)",
        days_ago=10,
        trigger=T.ANY_RANK_CHANGE,
        window=15,
        extension=5,
        forced_after=30,
        late_rounds=0,
        award_rank=1,
    ),
    PastAuction(
        "Reefer 40': frozen seafood",
        "Ho Chi Minh City, VN (VNSGN)",
        "Hamburg, DE (DEHAM)",
        days_ago=8,
        trigger=T.L1_RANK_CHANGE,
        window=10,
        extension=10,
        forced_after=40,
        late_rounds=2,
        award_rank=2,
    ),
    PastAuction(
        "FCL 40': apparel",
        "Chennai, IN (INMAA)",
        "Felixstowe, GB (GBFXT)",
        days_ago=6,
        trigger=T.BID_RECEIVED,
        window=10,
        extension=5,
        forced_after=30,
        late_rounds=0,
        award_rank=None,
    ),
    PastAuction(
        "FCL 2 x 40' HC: furniture",
        "Qingdao, CN (CNTAO)",
        "Santos, BR (BRSSZ)",
        days_ago=5,
        trigger=T.ANY_RANK_CHANGE,
        window=15,
        extension=5,
        forced_after=25,
        late_rounds=4,
        award_rank=1,
    ),
    PastAuction(
        "Air freight: pharma samples",
        "Mumbai, IN (BOM)",
        "Frankfurt, DE (FRA)",
        days_ago=3,
        trigger=T.L1_RANK_CHANGE,
        window=5,
        extension=5,
        forced_after=20,
        late_rounds=0,
        award_rank=1,
    ),
    PastAuction(
        "FCL 40': auto components",
        "Kaohsiung, TW (TWKHH)",
        "Antwerp, BE (BEANR)",
        days_ago=1,
        trigger=T.ANY_RANK_CHANGE,
        window=10,
        extension=5,
        forced_after=30,
        late_rounds=2,
        award_rank=None,
    ),
]


async def _create_users(session: AsyncSession) -> tuple[User, list[User]]:
    name, company, email = BUYER
    buyer = User(id=uuid.uuid7(), name=name, company=company, email=email, role=UserRole.BUYER)
    suppliers = [
        User(id=uuid.uuid7(), name=n, company=c, email=e, role=UserRole.SUPPLIER)
        for n, c, e in SUPPLIERS
    ]
    session.add_all([buyer, *suppliers])
    await session.commit()
    return buyer, suppliers


async def _replay_past_auction(
    session: AsyncSession,
    buyer: User,
    suppliers: list[User],
    spec: PastAuction,
    rng: random.Random,
    now: datetime,
) -> Rfq:
    start = (now - timedelta(days=spec.days_ago)).replace(minute=0, second=0, microsecond=0)
    close = start + timedelta(hours=2)
    data = RfqCreate(
        name=spec.name,
        origin=spec.origin,
        destination=spec.destination,
        currency="USD",
        pickup_date=(close + timedelta(days=7)).date(),
        bid_start_at=start,
        bid_close_at=close,
        forced_close_at=close + timedelta(minutes=spec.forced_after),
        trigger_window_minutes=spec.window,
        extension_minutes=spec.extension,
        extension_trigger=spec.trigger,
    )
    # one transaction per auction so the close task can't close it halfway
    rfq = await service.create_rfq(
        session, buyer, data, now=start - timedelta(days=1), enforce_future=False, commit=False
    )

    bidders = rng.sample(suppliers, k=rng.randint(3, len(suppliers)))
    carriers = {s.id: rng.choice(CARRIERS) for s in bidders}
    base = Decimal(rng.randrange(1800, 4200, 50))
    best: dict[uuid.UUID, Decimal] = {}
    span = close - start
    last_at = start

    async def bid(supplier: User, at: datetime, total: Decimal) -> None:
        nonlocal last_at
        quote = split_quote(rng, total.quantize(CENT), carriers[supplier.id], at.date())
        try:
            await service.place_bid(
                session, rfq.id, supplier, quote, clock=lambda: at, commit=False
            )
        except (ConflictError, BusinessRuleError):
            return
        best[supplier.id] = total.quantize(CENT)
        last_at = at

    def challenger() -> User:
        leader = min(best, key=lambda supplier_id: best[supplier_id])
        return rng.choice([s for s in bidders if s.id in best and s.id != leader])

    # opening bids
    fractions = sorted(rng.uniform(0.05, 0.45) for _ in bidders)
    for supplier, fraction in zip(bidders, fractions, strict=True):
        await bid(supplier, start + span * fraction, base * Decimal(str(rng.uniform(1.0, 1.15))))

    # a few improvements mid-auction
    for fraction in sorted(rng.uniform(0.5, 0.8) for _ in range(rng.randint(1, 3))):
        supplier = challenger()
        target = min(
            min(best.values()) * Decimal(str(rng.uniform(0.97, 0.995))), best[supplier.id] - 1
        )
        await bid(supplier, start + span * fraction, target)

    # late bids inside the trigger window
    for _ in range(spec.late_rounds):
        close_at = rfq.current_close_at
        window_start = close_at - timedelta(minutes=rfq.trigger_window_minutes)
        at = window_start + (close_at - window_start) * rng.uniform(0.25, 0.85)
        at = max(at, last_at + timedelta(seconds=rng.randint(30, 90)))
        if at >= close_at:
            break
        supplier = challenger()
        target = min(
            min(best.values()) * Decimal(str(rng.uniform(0.985, 0.995))), best[supplier.id] - 1
        )
        await bid(supplier, at, target)
    await session.commit()
    return rfq


async def _create_live_auctions(
    session: AsyncSession, buyer: User, suppliers: list[User], now: datetime
) -> None:
    oceanic, bluewave, transglobal, swift, horizon = suppliers
    minute = timedelta(minutes=1)

    async def scripted_bids(rfq: Rfq, script: list[tuple[int, User, str, str]]) -> None:
        rng = random.Random(rfq.reference_id)
        for offset, supplier, total, carrier in script:
            at = now + offset * minute
            quote = split_quote(rng, Decimal(total), carrier, at.date())
            await service.place_bid(session, rfq.id, supplier, quote, clock=lambda at=at: at)

    def payload(
        name: str,
        origin: str,
        destination: str,
        start: int,
        close: int,
        forced: int,
        window: int,
        extension: int,
        trigger: ExtensionTrigger,
    ) -> RfqCreate:
        return RfqCreate(
            name=name,
            origin=origin,
            destination=destination,
            currency="USD",
            pickup_date=(now + timedelta(days=12)).date(),
            bid_start_at=now + start * minute,
            bid_close_at=now + close * minute,
            forced_close_at=now + forced * minute,
            trigger_window_minutes=window,
            extension_minutes=extension,
            extension_trigger=trigger,
        )

    # active, ~40 min left (times are minutes from now)
    appliances = await service.create_rfq(
        session,
        buyer,
        payload(
            "FCL 40' HC: home appliances",
            "Shanghai, CN (CNSHA)",
            "Nhava Sheva, IN (INNSA)",
            start=-90,
            close=40,
            forced=80,
            window=10,
            extension=5,
            trigger=T.L1_RANK_CHANGE,
        ),
        now=now - 100 * minute,
    )
    await scripted_bids(
        appliances,
        [
            (-80, bluewave, "3420.00", "Maersk"),
            (-65, transglobal, "3385.00", "MSC"),
            (-50, swift, "3310.00", "CMA CGM"),
            (-30, bluewave, "3275.00", "Maersk"),
            (-12, horizon, "3290.00", "ONE"),
        ],
    )

    # active, inside the trigger window and already extended once
    fixtures = await service.create_rfq(
        session,
        buyer,
        payload(
            "LCL consolidation: retail fixtures",
            "Singapore (SGSIN)",
            "Jebel Ali, AE (AEJEA)",
            start=-60,
            close=12,
            forced=35,
            window=20,
            extension=5,
            trigger=T.ANY_RANK_CHANGE,
        ),
        now=now - 70 * minute,
    )
    await scripted_bids(
        fixtures,
        [
            (-50, transglobal, "1920.00", "Evergreen"),
            (-40, horizon, "1895.00", "ONE"),
            (-25, oceanic, "1880.00", "Hapag-Lloyd"),
            (-2, transglobal, "1862.50", "Evergreen"),
        ],
    )

    # upcoming
    await service.create_rfq(
        session,
        buyer,
        payload(
            "Reefer 40': fresh produce",
            "Laem Chabang, TH (THLCH)",
            "Sydney, AU (AUSYD)",
            start=180,
            close=300,
            forced=330,
            window=10,
            extension=5,
            trigger=T.BID_RECEIVED,
        ),
        now=now - 30 * minute,
    )


async def seed(factory: async_sessionmaker[AsyncSession], *, reset: bool = False) -> bool:
    now = utcnow()
    async with factory() as session:
        if reset:
            await session.execute(
                text("TRUNCATE auction_events, bids, rfqs, users RESTART IDENTITY CASCADE")
            )
            await session.execute(text("ALTER SEQUENCE rfq_reference_seq RESTART WITH 1"))
            await session.commit()
        elif await session.scalar(select(User.id).limit(1)) is not None:
            print("Seed skipped: the database already has data (use --reset to start over).")
            return False

        buyer, suppliers = await _create_users(session)
        rng = random.Random(20261121)
        past = [
            (spec, await _replay_past_auction(session, buyer, suppliers, spec, rng, now))
            for spec in PAST_AUCTIONS
        ]
        await service.close_due_auctions(session, now=now)
        for spec, rfq in past:
            if spec.award_rank is None:
                continue
            ranking = engine.rank_suppliers(await service.load_snapshots(session, rfq.id))
            choice = ranking[min(spec.award_rank, len(ranking)) - 1]
            await service.award_rfq(
                session,
                rfq.id,
                buyer,
                choice.best_bid.bid_id,
                now=rfq.current_close_at + timedelta(hours=3),
            )
        await _create_live_auctions(session, buyer, suppliers, now)
    return True


async def _main(reset: bool) -> None:
    db_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        if await seed(async_sessionmaker(db_engine, expire_on_commit=False), reset=reset):
            print(
                f"Seeded 1 buyer, {len(SUPPLIERS)} suppliers and {len(PAST_AUCTIONS) + 3} auctions."
            )
    finally:
        await db_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load demo data for the British Auction RFQ app.")
    parser.add_argument("--reset", action="store_true", help="delete existing users and auctions")
    asyncio.run(_main(parser.parse_args().reset))


if __name__ == "__main__":
    main()
