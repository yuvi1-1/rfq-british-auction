import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.auction import engine
from app.enums import AuctionStatus, ExtensionTrigger
from tests.helpers import SIX_PM, at

A, B, C = uuid.uuid7(), uuid.uuid7(), uuid.uuid7()
FORCED = at(18, 30)


def bid(supplier: uuid.UUID, total: str, placed_at: datetime) -> engine.BidSnapshot:
    return engine.BidSnapshot(uuid.uuid7(), supplier, Decimal(total), placed_at)


def decide(
    trigger: ExtensionTrigger,
    before: list[engine.BidSnapshot],
    new_bid: engine.BidSnapshot,
    *,
    close: datetime = SIX_PM,
    forced: datetime = FORCED,
) -> engine.ExtensionDecision:
    return engine.decide_extension(
        trigger=trigger,
        window_minutes=10,
        extension_minutes=5,
        current_close_at=close,
        forced_close_at=forced,
        now=new_bid.placed_at,
        before=engine.rank_suppliers(before),
        after=engine.rank_suppliers([*before, new_bid]),
    )


def test_ranking_uses_each_suppliers_best_bid_sorted_by_price() -> None:
    ranking = engine.rank_suppliers(
        [
            bid(A, "1000", at(17, 0)),
            bid(B, "950", at(17, 5)),
            bid(A, "900", at(17, 10)),  # A improves and overtakes B
            bid(C, "990", at(17, 15)),
        ]
    )
    assert [(r.rank, r.supplier_id, r.best_bid.total) for r in ranking] == [
        (1, A, Decimal("900")),
        (2, B, Decimal("950")),
        (3, C, Decimal("990")),
    ]


def test_ranking_tie_goes_to_the_earlier_bid() -> None:
    ranking = engine.rank_suppliers([bid(B, "800", at(17, 30)), bid(A, "800", at(17, 20))])
    assert [r.supplier_id for r in ranking] == [A, B]


def test_rank_changes_include_new_bidders() -> None:
    before = engine.rank_suppliers([bid(A, "900", at(17, 0))])
    after = engine.rank_suppliers([bid(A, "900", at(17, 0)), bid(B, "950", at(17, 5))])
    assert engine.rank_changes(before, after) == [engine.RankChange(B, None, 2)]


@pytest.mark.parametrize(
    ("now", "inside"),
    [
        (at(17, 49, 59), False),  # just before 5:50 PM
        (at(17, 50), True),  # window opens at close - X
        (at(17, 59, 59), True),
        (SIX_PM, False),  # at the close time bidding is over
    ],
)
def test_trigger_window_is_the_last_x_minutes(now: datetime, inside: bool) -> None:
    assert engine.in_trigger_window(now, SIX_PM, 10) is inside


def test_spec_example_bid_in_last_10_minutes_extends_6pm_to_605pm() -> None:
    decision = decide(
        ExtensionTrigger.BID_RECEIVED, [bid(A, "1000", at(17, 0))], bid(B, "1100", at(17, 55))
    )
    assert decision.triggered and decision.extended and not decision.capped
    assert decision.new_close_at == at(18, 5)


def test_bid_outside_the_window_never_extends() -> None:
    decision = decide(ExtensionTrigger.BID_RECEIVED, [], bid(A, "1000", at(17, 45)))
    assert not decision.in_window and not decision.extended
    assert decision.new_close_at == SIX_PM


def test_any_rank_change_ignores_price_cuts_that_keep_the_order() -> None:
    history = [bid(A, "900", at(17, 0)), bid(B, "1000", at(17, 5))]
    unchanged = decide(ExtensionTrigger.ANY_RANK_CHANGE, history, bid(B, "950", at(17, 58)))
    assert unchanged.in_window and not unchanged.triggered


def test_any_rank_change_spec_example_b_underbids_a() -> None:
    history = [bid(A, "900", at(17, 0)), bid(B, "1000", at(17, 5))]
    decision = decide(ExtensionTrigger.ANY_RANK_CHANGE, history, bid(B, "850", at(17, 58)))
    assert decision.extended and decision.new_close_at == at(18, 5)


def test_any_rank_change_counts_a_change_below_l1() -> None:
    history = [bid(A, "800", at(17, 0)), bid(B, "900", at(17, 5)), bid(C, "1000", at(17, 6))]
    decision = decide(ExtensionTrigger.ANY_RANK_CHANGE, history, bid(C, "850", at(17, 58)))
    assert decision.extended  # C moved L3 -> L2


def test_l1_change_ignores_rank_changes_below_l1() -> None:
    history = [bid(A, "800", at(17, 0)), bid(B, "900", at(17, 5)), bid(C, "1000", at(17, 6))]
    decision = decide(ExtensionTrigger.L1_RANK_CHANGE, history, bid(C, "850", at(17, 59)))
    assert not decision.triggered


def test_l1_change_spec_example_c_becomes_lowest_bidder() -> None:
    history = [bid(A, "800", at(17, 0)), bid(B, "900", at(17, 5)), bid(C, "1000", at(17, 6))]
    decision = decide(ExtensionTrigger.L1_RANK_CHANGE, history, bid(C, "750", at(17, 59)))
    assert decision.extended and decision.new_close_at == at(18, 5)


def test_first_ever_bid_in_window_is_an_l1_change() -> None:
    decision = decide(ExtensionTrigger.L1_RANK_CHANGE, [], bid(A, "1000", at(17, 55)))
    assert decision.extended


def test_extension_is_cut_short_at_the_forced_close_time() -> None:
    decision = decide(
        ExtensionTrigger.BID_RECEIVED, [], bid(A, "1000", at(17, 58)), forced=at(18, 3)
    )
    assert decision.extended and decision.capped
    assert decision.new_close_at == at(18, 3)


def test_no_extension_once_the_close_time_equals_the_forced_close() -> None:
    decision = decide(
        ExtensionTrigger.BID_RECEIVED,
        [],
        bid(A, "1000", at(18, 25)),
        close=FORCED,
        forced=FORCED,
    )
    assert decision.triggered and not decision.extended and decision.capped
    assert decision.new_close_at == FORCED


@pytest.mark.parametrize("trigger", list(ExtensionTrigger))
def test_no_trigger_ever_extends_past_forced_close(trigger: ExtensionTrigger) -> None:
    close, history = SIX_PM, [bid(A, "1000", at(17, 0))]
    price = 999
    for step in range(20):  # keep undercutting inside the moving window
        supplier = B if step % 2 == 0 else A
        new_bid = bid(supplier, str(price), close - timedelta(minutes=1))
        decision = decide(trigger, history, new_bid, close=close)
        history.append(new_bid)
        close = decision.new_close_at
        price -= 1
        assert close <= FORCED
    assert close == FORCED


@pytest.mark.parametrize(
    ("now", "close", "expected"),
    [
        (at(15, 59), SIX_PM, AuctionStatus.UPCOMING),
        (at(16, 0), SIX_PM, AuctionStatus.ACTIVE),
        (at(17, 59, 59), SIX_PM, AuctionStatus.ACTIVE),
        (SIX_PM, SIX_PM, AuctionStatus.CLOSED),
        (at(18, 15), at(18, 10), AuctionStatus.CLOSED),  # extended, then closed on its own
        (FORCED, FORCED, AuctionStatus.FORCE_CLOSED),  # ran all the way to the forced close
    ],
)
def test_derive_status(now: datetime, close: datetime, expected: AuctionStatus) -> None:
    status = engine.derive_status(
        now, bid_start_at=at(16, 0), current_close_at=close, forced_close_at=FORCED
    )
    assert status is expected
