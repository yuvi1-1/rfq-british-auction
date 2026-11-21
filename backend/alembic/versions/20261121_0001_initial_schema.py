"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum("BUYER", "SUPPLIER", name="user_role")
extension_trigger = sa.Enum(
    "BID_RECEIVED", "ANY_RANK_CHANGE", "L1_RANK_CHANGE", name="extension_trigger"
)
auction_event_type = sa.Enum(
    "RFQ_CREATED",
    "BID_PLACED",
    "AUCTION_EXTENDED",
    "EXTENSION_CAPPED",
    "AUCTION_CLOSED",
    "AUCTION_FORCE_CLOSED",
    "AUCTION_AWARDED",
    name="auction_event_type",
)


def upgrade() -> None:
    # RFQ-2026-0001, RFQ-2026-0002, ...
    op.execute("CREATE SEQUENCE rfq_reference_seq START 1")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "rfqs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(length=120), nullable=True),
        sa.Column("destination", sa.String(length=120), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("bid_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bid_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forced_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_window_minutes", sa.Integer(), nullable=False),
        sa.Column("extension_minutes", sa.Integer(), nullable=False),
        sa.Column("extension_trigger", extension_trigger, nullable=False),
        sa.Column("extension_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("awarded_bid_id", sa.Uuid(), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("bid_close_at > bid_start_at", name=op.f("ck_rfqs_close_after_start")),
        sa.CheckConstraint(
            "forced_close_at > bid_close_at", name=op.f("ck_rfqs_forced_after_close")
        ),
        sa.CheckConstraint(
            "current_close_at >= bid_close_at AND current_close_at <= forced_close_at",
            name=op.f("ck_rfqs_current_close_within_bounds"),
        ),
        sa.CheckConstraint(
            "trigger_window_minutes > 0", name=op.f("ck_rfqs_trigger_window_positive")
        ),
        sa.CheckConstraint(
            "extension_minutes > 0", name=op.f("ck_rfqs_extension_minutes_positive")
        ),
        sa.CheckConstraint(
            "extension_count >= 0", name=op.f("ck_rfqs_extension_count_non_negative")
        ),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], name=op.f("fk_rfqs_buyer_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rfqs")),
        sa.UniqueConstraint("reference_id", name=op.f("uq_rfqs_reference_id")),
    )
    op.create_index(
        "ix_rfqs_open_by_close_time",
        "rfqs",
        ["current_close_at"],
        postgresql_where=sa.text("closed_at IS NULL"),
    )

    op.create_table(
        "bids",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("carrier_name", sa.String(length=120), nullable=False),
        sa.Column("freight_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("origin_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("destination_charges", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=14, scale=2),
            sa.Computed("freight_charges + origin_charges + destination_charges", persisted=True),
            nullable=False,
        ),
        sa.Column("transit_time_days", sa.Integer(), nullable=False),
        sa.Column("quote_validity_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "freight_charges >= 0 AND origin_charges >= 0 AND destination_charges >= 0",
            name=op.f("ck_bids_charges_non_negative"),
        ),
        sa.CheckConstraint("transit_time_days > 0", name=op.f("ck_bids_transit_time_positive")),
        sa.ForeignKeyConstraint(
            ["rfq_id"], ["rfqs.id"], name=op.f("fk_bids_rfq_id_rfqs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["users.id"], name=op.f("fk_bids_supplier_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bids")),
    )
    op.create_index("ix_bids_rfq_id_total_amount", "bids", ["rfq_id", "total_amount", "created_at"])
    op.create_index("ix_bids_rfq_id_supplier_id", "bids", ["rfq_id", "supplier_id", "created_at"])

    # added here because rfqs and bids reference each other
    op.create_foreign_key("fk_rfqs_awarded_bid_id_bids", "rfqs", "bids", ["awarded_bid_id"], ["id"])

    op.create_table(
        "auction_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", auction_event_type, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("bid_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_auction_events_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["bid_id"], ["bids.id"], name=op.f("fk_auction_events_bid_id_bids"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["rfq_id"], ["rfqs.id"], name=op.f("fk_auction_events_rfq_id_rfqs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auction_events")),
    )
    op.create_index(
        "ix_auction_events_rfq_id_occurred_at", "auction_events", ["rfq_id", "occurred_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_auction_events_rfq_id_occurred_at", table_name="auction_events")
    op.drop_table("auction_events")
    op.drop_constraint("fk_rfqs_awarded_bid_id_bids", "rfqs", type_="foreignkey")
    op.drop_index("ix_bids_rfq_id_supplier_id", table_name="bids")
    op.drop_index("ix_bids_rfq_id_total_amount", table_name="bids")
    op.drop_table("bids")
    op.drop_index("ix_rfqs_open_by_close_time", table_name="rfqs")
    op.drop_table("rfqs")
    op.drop_table("users")
    bind = op.get_bind()
    for enum_type in (auction_event_type, extension_trigger, user_role):
        enum_type.drop(bind, checkfirst=True)
    op.execute("DROP SEQUENCE IF EXISTS rfq_reference_seq")
