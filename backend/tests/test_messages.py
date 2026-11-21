import json

from app.auction import messages
from app.enums import EventType

ALPHA, BETA, GAMMA = "id-alpha", "id-beta", "id-gamma"

EXTENSION = {
    "trigger": "ANY_RANK_CHANGE",
    "trigger_window_minutes": 10,
    "extension_minutes": 5,
    "old_close_at": "2026-11-21T18:00:00+00:00",
    "new_close_at": "2026-11-21T18:05:00+00:00",
    "forced_close_at": "2026-11-21T18:30:00+00:00",
    "capped": False,
    "added_seconds": 300.0,
    "supplier_id": BETA,
    "supplier_name": "Beta Freight",
    "rank_changes": [
        {"supplier_id": BETA, "supplier_name": "Beta Freight", "old_rank": 2, "new_rank": 1},
        {"supplier_id": ALPHA, "supplier_name": "Alpha Cargo", "old_rank": 1, "new_rank": 2},
    ],
    "previous_l1": {"supplier_id": ALPHA, "supplier_name": "Alpha Cargo"},
    "new_l1": {"supplier_id": BETA, "supplier_name": "Beta Freight"},
}

BID = {
    "supplier_id": BETA,
    "supplier_name": "Beta Freight",
    "carrier_name": "MSC",
    "total": "1234.50",
    "currency": "USD",
    "rank": 1,
    "previous_rank": 2,
    "became_l1": True,
    "in_trigger_window": True,
}


def test_buyer_sees_who_moved_and_why_the_auction_extended() -> None:
    text = messages.render(EventType.AUCTION_EXTENDED, EXTENSION)
    assert text == (
        "Auction extended by 5 min: supplier ranking changed within the last 10 min "
        "(Beta Freight L2 → L1, Alpha Cargo L1 → L2)."
    )


def test_supplier_sees_only_their_own_rank_change() -> None:
    text = messages.render(EventType.AUCTION_EXTENDED, EXTENSION, ALPHA)
    assert text.endswith("(you: L1 → L2).")
    assert "Beta" not in text


def test_bid_messages_for_buyer_bidder_and_competitor() -> None:
    assert messages.render(EventType.BID_PLACED, BID) == (
        "Beta Freight lowered their bid to USD 1,234.50 (MSC), moved L2 → L1."
    )
    assert messages.render(EventType.BID_PLACED, BID, BETA) == (
        "You lowered your bid to USD 1,234.50 (MSC), moved L2 → L1."
    )
    assert messages.render(EventType.BID_PLACED, BID, GAMMA) == (
        "A competitor placed a bid and took L1."
    )


def test_sanitized_details_hide_competitor_names_and_prices() -> None:
    for event_type, details in [
        (EventType.AUCTION_EXTENDED, EXTENSION),
        (EventType.BID_PLACED, BID),
    ]:
        safe = json.dumps(messages.sanitize(event_type, details, GAMMA))
        assert "Beta" not in safe and "Alpha" not in safe and "1234.50" not in safe


def test_capped_extension_and_duration_text() -> None:
    capped = {**EXTENSION, "capped": True, "added_seconds": 150.0}
    assert messages.render(EventType.AUCTION_EXTENDED, capped).startswith(
        "Auction extended by 2 min 30 s:"
    )
    assert "cut short at the forced close time" in messages.render(
        EventType.AUCTION_EXTENDED, capped
    )
