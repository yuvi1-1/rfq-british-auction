import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.enums import EventType, ExtensionTrigger, UserRole

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

MONEY = Numeric(14, 2)
TIMESTAMPTZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(enum_cls, name=name, values_callable=lambda members: [m.value for m in members])


class User(Base):
    """A buyer (creates RFQs, awards them) or a supplier (submits quotes)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())


class Rfq(Base):
    """An RFQ run as a British (reverse) auction."""

    __tablename__ = "rfqs"
    __table_args__ = (
        CheckConstraint("bid_close_at > bid_start_at", name="close_after_start"),
        CheckConstraint("forced_close_at > bid_close_at", name="forced_after_close"),
        # extensions can't go past the forced close
        CheckConstraint(
            "current_close_at >= bid_close_at AND current_close_at <= forced_close_at",
            name="current_close_within_bounds",
        ),
        CheckConstraint("trigger_window_minutes > 0", name="trigger_window_positive"),
        CheckConstraint("extension_minutes > 0", name="extension_minutes_positive"),
        CheckConstraint("extension_count >= 0", name="extension_count_non_negative"),
        # used by the close task
        Index(
            "ix_rfqs_open_by_close_time",
            "current_close_at",
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    reference_id: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    origin: Mapped[str | None] = mapped_column(String(120))
    destination: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    pickup_date: Mapped[date] = mapped_column(Date)

    bid_start_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    bid_close_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)  # as created, never changes
    current_close_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)  # moves with extensions
    forced_close_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)  # hard stop

    trigger_window_minutes: Mapped[int] = mapped_column(Integer)  # X
    extension_minutes: Mapped[int] = mapped_column(Integer)  # Y
    extension_trigger: Mapped[ExtensionTrigger] = mapped_column(
        pg_enum(ExtensionTrigger, "extension_trigger")
    )
    extension_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # set by the close task
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    awarded_bid_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bids.id", use_alter=True, name="fk_rfqs_awarded_bid_id_bids")
    )
    awarded_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now()
    )


class Bid(Base):
    """One quote submission. A supplier can submit many; their lowest one counts for ranking."""

    __tablename__ = "bids"
    __table_args__ = (
        CheckConstraint(
            "freight_charges >= 0 AND origin_charges >= 0 AND destination_charges >= 0",
            name="charges_non_negative",
        ),
        CheckConstraint("transit_time_days > 0", name="transit_time_positive"),
        Index("ix_bids_rfq_id_total_amount", "rfq_id", "total_amount", "created_at"),
        Index("ix_bids_rfq_id_supplier_id", "rfq_id", "supplier_id", "created_at"),
    )
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012 (fetch the generated total on INSERT)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    rfq_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    carrier_name: Mapped[str] = mapped_column(String(120))
    freight_charges: Mapped[Decimal] = mapped_column(MONEY)
    origin_charges: Mapped[Decimal] = mapped_column(MONEY)
    destination_charges: Mapped[Decimal] = mapped_column(MONEY)
    total_amount: Mapped[Decimal] = mapped_column(
        MONEY, Computed("freight_charges + origin_charges + destination_charges", persisted=True)
    )
    transit_time_days: Mapped[int] = mapped_column(Integer)
    quote_validity_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)

    supplier: Mapped[User] = relationship(lazy="joined")


class AuctionEvent(Base):
    """Append-only activity log: bids, extensions (with reasons), closes and awards."""

    __tablename__ = "auction_events"
    __table_args__ = (Index("ix_auction_events_rfq_id_occurred_at", "rfq_id", "occurred_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    event_type: Mapped[EventType] = mapped_column(pg_enum(EventType, "auction_event_type"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    bid_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bids.id", ondelete="SET NULL"))
    # buyer wording; suppliers get a filtered version (see messages.py)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())

    actor: Mapped[User | None] = relationship(lazy="joined")
