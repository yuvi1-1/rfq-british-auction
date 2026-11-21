from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.enums import AuctionStatus, EventType, ExtensionTrigger, UserRole

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    company: str
    email: str
    role: UserRole


class RfqCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=200)
    reference_id: str | None = Field(
        default=None, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,39}$"
    )
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    currency: Literal["USD", "EUR", "INR"] = "USD"
    pickup_date: date
    bid_start_at: AwareDatetime
    bid_close_at: AwareDatetime
    forced_close_at: AwareDatetime
    trigger_window_minutes: int = Field(ge=1, le=1440, description="X: trigger window")
    extension_minutes: int = Field(ge=1, le=1440, description="Y: extension duration")
    extension_trigger: ExtensionTrigger

    @field_validator("reference_id", "origin", "destination", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("bid_start_at", "bid_close_at", "forced_close_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("bid_close_at")
    @classmethod
    def _close_after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("bid_start_at")
        if start is not None and value <= start:
            raise ValueError("Bid close time must be later than the bid start time")
        return value

    @field_validator("forced_close_at")
    @classmethod
    def _forced_after_close(cls, value: datetime, info: ValidationInfo) -> datetime:
        close = info.data.get("bid_close_at")
        if close is not None and value <= close:
            raise ValueError("Forced bid close time must be later than the bid close time")
        return value


class BidCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    carrier_name: str = Field(min_length=2, max_length=120)
    freight_charges: Money
    origin_charges: Money
    destination_charges: Money
    transit_time_days: int = Field(ge=1, le=365)
    quote_validity_date: date

    @model_validator(mode="after")
    def _positive_total(self) -> Self:
        if self.total <= 0:
            raise ValueError("Total charges must be greater than zero")
        return self

    @property
    def total(self) -> Decimal:
        return self.freight_charges + self.origin_charges + self.destination_charges


class AwardCreate(BaseModel):
    bid_id: UUID


class DemoAuctionCreate(BaseModel):
    extension_trigger: ExtensionTrigger = ExtensionTrigger.L1_RANK_CHANGE
    duration_minutes: int = Field(default=3, ge=2, le=30)
    trigger_window_minutes: int = Field(default=2, ge=1, le=10)
    extension_minutes: int = Field(default=1, ge=1, le=10)
    forced_close_after_minutes: int = Field(
        default=4, ge=1, le=30, description="Forced close = bid close + this many minutes"
    )

    @model_validator(mode="after")
    def _window_fits(self) -> Self:
        if self.trigger_window_minutes > self.duration_minutes:
            raise ValueError("The trigger window cannot be longer than the auction itself")
        return self


class AuctionConfigOut(BaseModel):
    trigger_window_minutes: int
    extension_minutes: int
    extension_trigger: ExtensionTrigger


class RfqSummary(BaseModel):
    id: UUID
    reference_id: str
    name: str
    origin: str | None
    destination: str | None
    currency: str
    pickup_date: date
    bid_start_at: datetime
    bid_close_at: datetime
    current_close_at: datetime
    forced_close_at: datetime
    status: AuctionStatus
    config: AuctionConfigOut
    lowest_bid: Decimal | None
    bid_count: int
    supplier_count: int
    extension_count: int
    is_awarded: bool
    my_rank: int | None = None  # only filled in for suppliers


class BidOut(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    carrier_name: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total_amount: Decimal
    transit_time_days: int
    quote_validity_date: date
    created_at: datetime
    is_best: bool  # the supplier's current best bid, i.e. the one that counts for ranking


class RankingEntryOut(BaseModel):
    rank: int
    supplier_id: UUID
    supplier_name: str
    bid_count: int
    bid: BidOut


class SupplierPositionOut(BaseModel):
    rank: int | None
    total_suppliers: int
    best_bid: BidOut | None
    l1_total: Decimal | None
    gap_to_l1: Decimal | None
    is_l1: bool


class EventOut(BaseModel):
    id: int
    event_type: EventType
    occurred_at: datetime
    actor_name: str | None
    message: str
    details: dict[str, Any]


class AwardOut(BaseModel):
    awarded_at: datetime
    awarded_to_me: bool | None = None  # suppliers only
    bid_id: UUID | None = None  # hidden from suppliers who did not win
    supplier_name: str | None = None
    carrier_name: str | None = None
    total_amount: Decimal | None = None


class RfqDetail(RfqSummary):
    viewer_role: UserRole
    buyer_company: str
    ranking: list[RankingEntryOut]  # buyers only: one row per supplier (their best bid)
    bids: list[BidOut]  # buyers: every bid; suppliers: their own bids
    my_position: SupplierPositionOut | None
    events: list[EventOut]
    award: AwardOut | None
    can_bid: bool
    can_award: bool


class BidPlacedOut(BaseModel):
    bid: BidOut
    rank: int
    total_suppliers: int
    extended: bool
    current_close_at: datetime
    message: str


class DemoAuctionOut(BaseModel):
    rfq: RfqSummary
    bots_started: bool


class MetricsSummary(BaseModel):
    total_auctions: int
    upcoming_auctions: int
    active_auctions: int
    ended_auctions: int
    total_bids: int
    total_extensions: int
    avg_bids_per_rfq: float | None
    avg_suppliers_per_rfq: float | None
    avg_price_improvement_pct: float | None
    extended_share_pct: float | None
    late_bid_share_pct: float | None


class CohortStats(BaseModel):
    auctions: int
    avg_bids_per_rfq: float | None
    avg_suppliers_per_rfq: float | None
    avg_price_improvement_pct: float | None


class AuctionMetricsRow(BaseModel):
    id: UUID
    reference_id: str
    name: str
    status: AuctionStatus
    currency: str
    bid_count: int
    supplier_count: int
    extension_count: int
    opening_price: Decimal | None
    final_price: Decimal | None
    price_improvement_pct: float | None
    ended_at: datetime | None


class MetricsOut(BaseModel):
    summary: MetricsSummary
    extended: CohortStats
    not_extended: CohortStats
    auctions: list[AuctionMetricsRow]
