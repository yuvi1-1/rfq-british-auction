# Database Schema

PostgreSQL. Migrations are managed with Alembic (`backend/alembic`).

```mermaid
erDiagram
    direction LR
    users ||--o{ rfqs : creates
    users ||--o{ bids : submits
    rfqs ||--o{ bids : has
    rfqs ||--o{ auction_events : has
    bids |o--o{ auction_events : ""
    users |o--o{ auction_events : ""

    users {
        uuid id PK
        varchar name
        varchar company
        varchar email UK
        user_role role "BUYER or SUPPLIER"
        timestamptz created_at
    }
    rfqs {
        uuid id PK
        varchar reference_id UK
        varchar name
        uuid buyer_id FK
        varchar origin
        varchar destination
        varchar currency
        date pickup_date
        timestamptz bid_start_at
        timestamptz bid_close_at "original close time"
        timestamptz current_close_at "after extensions"
        timestamptz forced_close_at
        int trigger_window_minutes "X"
        int extension_minutes "Y"
        extension_trigger extension_trigger
        int extension_count
        timestamptz closed_at
        uuid awarded_bid_id FK
        timestamptz awarded_at
        timestamptz created_at
        timestamptz updated_at
    }
    bids {
        uuid id PK
        uuid rfq_id FK
        uuid supplier_id FK
        varchar carrier_name
        numeric freight_charges
        numeric origin_charges
        numeric destination_charges
        numeric total_amount "generated"
        int transit_time_days
        date quote_validity_date
        timestamptz created_at
    }
    auction_events {
        bigint id PK
        uuid rfq_id FK
        auction_event_type event_type
        uuid actor_id FK
        uuid bid_id FK
        text message
        jsonb details
        timestamptz occurred_at
        timestamptz created_at
    }
```

## Tables

- **users**: buyers and suppliers.
- **rfqs**: one row per RFQ / auction. `bid_close_at` keeps the original close time and
  `current_close_at` moves when the auction is extended. `closed_at` is set by the Celery task
  once the close is logged.
- **bids**: one row per quote. `total_amount` is a generated column
  (`freight_charges + origin_charges + destination_charges`).
- **auction_events**: activity log. Bids, extensions (with the reason), closes and awards.
  `details` holds structured data such as the old and new close time.

## Enums

- `user_role`: `BUYER`, `SUPPLIER`
- `extension_trigger`: `BID_RECEIVED`, `ANY_RANK_CHANGE`, `L1_RANK_CHANGE`
- `auction_event_type`: `RFQ_CREATED`, `BID_PLACED`, `AUCTION_EXTENDED`, `EXTENSION_CAPPED`,
  `AUCTION_CLOSED`, `AUCTION_FORCE_CLOSED`, `AUCTION_AWARDED`

## Constraints

- `forced_close_at > bid_close_at > bid_start_at`
- `bid_close_at <= current_close_at <= forced_close_at` (extensions can't go past the forced close)
- `trigger_window_minutes > 0`, `extension_minutes > 0`
- charges `>= 0`, `transit_time_days > 0`

## Indexes

- `bids (rfq_id, total_amount, created_at)`: ranking and lowest bid per RFQ
- `bids (rfq_id, supplier_id, created_at)`: a supplier's bids on an RFQ
- `rfqs (current_close_at) WHERE closed_at IS NULL`: used by the close task
- `auction_events (rfq_id, occurred_at, id)`: activity log
