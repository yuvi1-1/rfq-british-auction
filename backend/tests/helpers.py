import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auction import service
from app.enums import ExtensionTrigger, UserRole
from app.models import Rfq, User
from app.schemas import RfqCreate

# example from the assignment: close at 6:00 PM, X = 10 min, Y = 5 min
SIX_PM = datetime(2026, 11, 21, 18, 0, tzinfo=UTC)
CENT = Decimal("0.01")


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return SIX_PM.replace(hour=hour, minute=minute, second=second)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def set(self, value: datetime) -> None:
        self.now = value

    def advance(self, **delta: float) -> datetime:
        self.now += timedelta(**delta)
        return self.now


@dataclass
class RecordingPublisher:
    messages: list[dict[str, Any]] = field(default_factory=list)

    async def publish(self, message: dict[str, Any]) -> None:
        self.messages.append(message)


@dataclass
class RecordingLauncher:
    launched: list[uuid.UUID] = field(default_factory=list)

    async def __call__(self, rfq_id: uuid.UUID) -> bool:
        self.launched.append(rfq_id)
        return True


@dataclass
class World:
    buyer: User
    suppliers: list[User]

    @property
    def a(self) -> User:
        return self.suppliers[0]

    @property
    def b(self) -> User:
        return self.suppliers[1]

    @property
    def c(self) -> User:
        return self.suppliers[2]


async def make_users(session: AsyncSession, supplier_count: int = 5) -> World:
    buyer = User(
        id=uuid.uuid7(),
        name="Bea Buyer",
        company="Buyer Co",
        email="buyer@example.test",
        role=UserRole.BUYER,
    )
    suppliers = [
        User(
            id=uuid.uuid7(),
            name=f"Supplier {i}",
            company=f"Supplier {chr(65 + i)} Ltd",
            email=f"supplier{i}@example.test",
            role=UserRole.SUPPLIER,
        )
        for i in range(supplier_count)
    ]
    session.add_all([buyer, *suppliers])
    await session.commit()
    return World(buyer, suppliers)


async def make_rfq(
    session: AsyncSession,
    buyer: User,
    *,
    start: datetime = at(16, 0),
    close: datetime = SIX_PM,
    forced: datetime = at(18, 30),
    window: int = 10,
    extension: int = 5,
    trigger: ExtensionTrigger = ExtensionTrigger.BID_RECEIVED,
    name: str = "FCL 40' Shanghai to Mumbai",
) -> Rfq:
    data = RfqCreate(
        name=name,
        origin="Shanghai",
        destination="Mumbai",
        pickup_date=date(2026, 12, 15),
        bid_start_at=start,
        bid_close_at=close,
        forced_close_at=forced,
        trigger_window_minutes=window,
        extension_minutes=extension,
        extension_trigger=trigger,
    )
    return await service.create_rfq(session, buyer, data, now=start, enforce_future=False)


def quote(
    total: str | int, carrier: str = "Maersk", validity: str = "2026-12-31"
) -> dict[str, Any]:
    """A quote whose freight / origin / destination charges add up to `total`."""
    total_amount = Decimal(str(total))
    freight = (total_amount * Decimal("0.8")).quantize(CENT)
    origin = (total_amount * Decimal("0.1")).quantize(CENT)
    return {
        "carrier_name": carrier,
        "freight_charges": str(freight),
        "origin_charges": str(origin),
        "destination_charges": str(total_amount - freight - origin),
        "transit_time_days": 21,
        "quote_validity_date": validity,
    }


def as_user(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}
