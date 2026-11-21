from decimal import Decimal
from typing import Any

from app.enums import EventType, ExtensionTrigger

Details = dict[str, Any]

TRIGGER_CONDITIONS = {
    ExtensionTrigger.BID_RECEIVED: "a bid is received",
    ExtensionTrigger.ANY_RANK_CHANGE: "any supplier's rank changes",
    ExtensionTrigger.L1_RANK_CHANGE: "the lowest bidder (L1) changes",
}

# extension fields that suppliers can see
_PUBLIC_EXTENSION_KEYS = (
    "trigger",
    "trigger_window_minutes",
    "extension_minutes",
    "old_close_at",
    "new_close_at",
    "forced_close_at",
    "capped",
    "added_seconds",
)


def money(currency: str, amount: str | Decimal) -> str:
    return f"{currency} {Decimal(amount):,.2f}"


def duration_text(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    if secs == 0:
        return f"{minutes} min"
    if minutes == 0:
        return f"{secs} s"
    return f"{minutes} min {secs} s"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _rank_move(change: Details) -> str:
    old = change.get("old_rank")
    return f"new → L{change['new_rank']}" if old is None else f"L{old} → L{change['new_rank']}"


def render(event_type: EventType, details: Details, viewer_supplier_id: str | None = None) -> str:
    """Render an event. `viewer_supplier_id=None` is the full (buyer) view."""
    match event_type:
        case EventType.RFQ_CREATED:
            return _rfq_created(details)
        case EventType.BID_PLACED:
            return _bid_placed(details, viewer_supplier_id)
        case EventType.AUCTION_EXTENDED:
            text = (
                f"Auction extended by {duration_text(details['added_seconds'])}: "
                f"{_extension_reason(details, viewer_supplier_id)}."
            )
            if details.get("capped"):
                text += " The extension was cut short at the forced close time."
            return text
        case EventType.EXTENSION_CAPPED:
            return (
                f"No extension: {_extension_reason(details, viewer_supplier_id)}, but the auction "
                "has already reached its forced close time."
            )
        case EventType.AUCTION_CLOSED | EventType.AUCTION_FORCE_CLOSED:
            return _closed(details, viewer_supplier_id)
        case EventType.AUCTION_AWARDED:
            return _awarded(details, viewer_supplier_id)
    return event_type.value


def _rfq_created(d: Details) -> str:
    condition = TRIGGER_CONDITIONS[ExtensionTrigger(d["trigger"])]
    return (
        f"RFQ created. The bid close time extends by {d['extension_minutes']} min if {condition} "
        f"within the last {d['trigger_window_minutes']} min, up to the forced close time."
    )


def _bid_placed(d: Details, viewer: str | None) -> str:
    mine = viewer is not None and d["supplier_id"] == viewer
    if viewer is not None and not mine:
        return (
            "A competitor placed a bid and took L1."
            if d.get("became_l1")
            else ("A competitor placed a bid.")
        )

    who = "You" if mine else d["supplier_name"]
    price = money(d["currency"], d["total"])
    rank, previous = d["rank"], d.get("previous_rank")
    if previous is None:
        return f"{who} placed a first bid of {price} ({d['carrier_name']}), ranked L{rank}."
    lowered = "lowered your bid" if mine else "lowered their bid"
    position = f"still L{rank}" if previous == rank else f"moved L{previous} → L{rank}"
    return f"{who} {lowered} to {price} ({d['carrier_name']}), {position}."


def _extension_reason(d: Details, viewer: str | None) -> str:
    window = d["trigger_window_minutes"]
    match ExtensionTrigger(d["trigger"]):
        case ExtensionTrigger.BID_RECEIVED:
            if viewer is None:
                return f"{d['supplier_name']} bid within the last {window} min"
            whose = "your" if d.get("supplier_id") == viewer else "a"
            return f"{whose} bid arrived within the last {window} min"
        case ExtensionTrigger.ANY_RANK_CHANGE:
            reason = f"supplier ranking changed within the last {window} min"
            changes = d.get("rank_changes", [])
            if viewer is None:
                listed = ", ".join(f"{c['supplier_name']} {_rank_move(c)}" for c in changes)
                return f"{reason} ({listed})" if listed else reason
            mine = next((c for c in changes if c.get("supplier_id") == viewer), None)
            return f"{reason} (you: {_rank_move(mine)})" if mine else reason
        case ExtensionTrigger.L1_RANK_CHANGE:
            new_l1, previous_l1 = d.get("new_l1") or {}, d.get("previous_l1")
            if viewer is None:
                if previous_l1 is None:
                    return (
                        f"{new_l1.get('supplier_name')} became the first L1 "
                        f"within the last {window} min"
                    )
                return (
                    f"{new_l1.get('supplier_name')} replaced {previous_l1['supplier_name']} "
                    f"as L1 within the last {window} min"
                )
            if new_l1.get("supplier_id") == viewer:
                return f"you became L1 within the last {window} min"
            if previous_l1 and previous_l1.get("supplier_id") == viewer:
                return f"you lost L1 within the last {window} min"
            return f"the lowest bidder (L1) changed within the last {window} min"
    return "the trigger condition was met"


def _closed(d: Details, viewer: str | None) -> str:
    forced = d.get("forced", False)
    head = "Auction force-closed at the forced close time." if forced else "Auction closed."
    l1 = d.get("l1")
    if not l1:
        return f"{head} No bids were received."
    price = money(d["currency"], l1["total"])
    if viewer is None:
        bids, suppliers = plural(d["bid_count"], "bid"), plural(d["supplier_count"], "supplier")
        return f"{head} {bids} from {suppliers}. Final L1: {l1['supplier_name']} at {price}."
    your_rank = (d.get("final_ranks") or {}).get(viewer)
    tail = f" You finished L{your_rank}." if your_rank else ""
    return f"{head} Final L1 price: {price}.{tail}"


def _awarded(d: Details, viewer: str | None) -> str:
    price = money(d["currency"], d["total"])
    if viewer is None:
        who = f"{d['supplier_name']} ({d['carrier_name']})"
        return f"Awarded to {who} at {price}, ranked L{d['rank']}."
    if d.get("supplier_id") == viewer:
        return f"You were awarded this RFQ at {price}."
    return "This RFQ was awarded to another supplier."


def sanitize(event_type: EventType, details: Details, viewer_supplier_id: str) -> Details:
    """Strip competitor identities and prices from event details before a supplier sees them."""
    viewer = viewer_supplier_id
    match event_type:
        case EventType.RFQ_CREATED:
            return details
        case EventType.BID_PLACED:
            if details.get("supplier_id") == viewer:
                return details
            return {k: details[k] for k in ("became_l1", "in_trigger_window") if k in details}
        case EventType.AUCTION_EXTENDED | EventType.EXTENSION_CAPPED:
            public = {k: details[k] for k in _PUBLIC_EXTENSION_KEYS if k in details}
            changes = details.get("rank_changes", [])
            mine = next((c for c in changes if c.get("supplier_id") == viewer), None)
            if mine:
                public["your_rank_change"] = {
                    "old_rank": mine.get("old_rank"),
                    "new_rank": mine["new_rank"],
                }
            return public
        case EventType.AUCTION_CLOSED | EventType.AUCTION_FORCE_CLOSED:
            l1 = details.get("l1") or {}
            return {
                "closed_at": details.get("closed_at"),
                "forced": details.get("forced"),
                "bid_count": details.get("bid_count"),
                "supplier_count": details.get("supplier_count"),
                "extension_count": details.get("extension_count"),
                "l1_total": l1.get("total"),
                "your_rank": (details.get("final_ranks") or {}).get(viewer),
            }
        case EventType.AUCTION_AWARDED:
            if details.get("supplier_id") == viewer:
                return {"awarded_to_you": True, "total": details.get("total")}
            return {"awarded_to_you": False}
    return {}
