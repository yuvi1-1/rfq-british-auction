from enum import StrEnum


class UserRole(StrEnum):
    BUYER = "BUYER"
    SUPPLIER = "SUPPLIER"


class ExtensionTrigger(StrEnum):
    """What kind of activity inside the trigger window extends the auction (PDF section 6.3)."""

    BID_RECEIVED = "BID_RECEIVED"  # (a) any new bid in the last X minutes
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"  # (b) any supplier's rank changes in the last X minutes
    L1_RANK_CHANGE = "L1_RANK_CHANGE"  # (c) the lowest bidder (L1) changes in the last X minutes


class AuctionStatus(StrEnum):
    UPCOMING = "UPCOMING"  # bid start time not reached yet
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"  # ended at its (possibly extended) bid close time
    FORCE_CLOSED = "FORCE_CLOSED"  # ended because it reached the forced bid close time


class EventType(StrEnum):
    RFQ_CREATED = "RFQ_CREATED"
    BID_PLACED = "BID_PLACED"
    AUCTION_EXTENDED = "AUCTION_EXTENDED"
    EXTENSION_CAPPED = (
        "EXTENSION_CAPPED"  # trigger fired but the forced close time was already reached
    )
    AUCTION_CLOSED = "AUCTION_CLOSED"
    AUCTION_FORCE_CLOSED = "AUCTION_FORCE_CLOSED"
    AUCTION_AWARDED = "AUCTION_AWARDED"
