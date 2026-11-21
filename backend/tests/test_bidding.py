import asyncio
import itertools
from datetime import timedelta

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.enums import EventType, ExtensionTrigger
from app.models import AuctionEvent, Rfq, User
from tests.helpers import (
    SIX_PM,
    FakeClock,
    RecordingPublisher,
    World,
    as_user,
    at,
    make_rfq,
    make_users,
    quote,
)


async def bid(client: AsyncClient, rfq: Rfq, supplier: User, total: int | str) -> Response:
    return await client.post(
        f"/api/rfqs/{rfq.id}/bids", json=quote(total), headers=as_user(supplier)
    )


async def close_time(client: AsyncClient, rfq: Rfq, world: World) -> str:
    body = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.buyer))).json()
    return body["current_close_at"]


async def events_of(session: AsyncSession, rfq: Rfq, event_type: EventType) -> list[AuctionEvent]:
    result = await session.scalars(
        select(AuctionEvent)
        .where(AuctionEvent.rfq_id == rfq.id, AuctionEvent.event_type == event_type)
        .order_by(AuctionEvent.id)
        .execution_options(populate_existing=True)
    )
    return list(result.all())


async def test_bids_are_rejected_before_start_and_after_close(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer)
    clock.set(at(15, 59))
    early = await bid(client, rfq, world.a, 1000)
    assert early.status_code == 409 and "not started" in early.json()["detail"]

    clock.set(SIX_PM)  # bidding stops exactly at the close time
    late = await bid(client, rfq, world.a, 1000)
    assert late.status_code == 409 and "closed" in late.json()["detail"]


async def test_only_suppliers_bid(client: AsyncClient, session: AsyncSession, world: World) -> None:
    rfq = await make_rfq(session, world.buyer)
    response = await bid(client, rfq, world.buyer, 1000)
    assert response.status_code == 403


async def test_a_new_bid_must_beat_the_suppliers_own_best(
    client: AsyncClient, session: AsyncSession, world: World
) -> None:
    rfq = await make_rfq(session, world.buyer)
    assert (await bid(client, rfq, world.a, 1000)).status_code == 201
    same = await bid(client, rfq, world.a, 1000)
    assert same.status_code == 422
    assert "must be lower than your current best (USD 1,000.00)" in same.json()["detail"]
    assert (await bid(client, rfq, world.a, 999)).status_code == 201


async def test_quote_fields_are_validated(
    client: AsyncClient, session: AsyncSession, world: World
) -> None:
    rfq = await make_rfq(session, world.buyer)
    payload = {**quote(1000), "freight_charges": "-5", "transit_time_days": 0}
    response = await client.post(f"/api/rfqs/{rfq.id}/bids", json=payload, headers=as_user(world.a))
    assert response.status_code == 422
    assert {e["loc"][-1] for e in response.json()["detail"]} == {
        "freight_charges",
        "transit_time_days",
    }

    expired = {**quote(1000), "quote_validity_date": "2026-11-20"}
    response = await client.post(f"/api/rfqs/{rfq.id}/bids", json=expired, headers=as_user(world.a))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "quote_validity_date"


async def test_bid_outside_trigger_window_does_not_extend(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer)
    clock.set(at(17, 49))  # window is 5:50-6:00 PM
    response = await bid(client, rfq, world.a, 1000)
    assert response.json()["extended"] is False
    assert (await close_time(client, rfq, world)).startswith("2026-11-21T18:00")


async def test_bid_received_trigger_matches_the_spec_example(
    client: AsyncClient,
    session: AsyncSession,
    world: World,
    clock: FakeClock,
    publisher: RecordingPublisher,
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.BID_RECEIVED)
    await bid(client, rfq, world.a, 1000)
    clock.set(at(17, 55))  # "A bid is placed at 5:55 PM"
    response = await bid(client, rfq, world.b, 1100)  # even a non-winning bid counts
    body = response.json()
    assert body["extended"] is True
    assert body["current_close_at"].startswith("2026-11-21T18:05")  # 6:00 PM -> 6:05 PM
    assert body["message"].endswith("Your bid extended the auction by 5 min.")

    [event] = await events_of(session, rfq, EventType.AUCTION_EXTENDED)
    assert event.details["old_close_at"].startswith("2026-11-21T18:00")
    assert event.details["new_close_at"].startswith("2026-11-21T18:05")
    assert event.message == (
        f"Auction extended by 5 min: {world.b.company} bid within the last 10 min."
    )
    live = publisher.messages[-1]
    assert live["type"] == "bid_placed" and live["extension"]["extended"] is True


async def test_any_rank_change_trigger(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.ANY_RANK_CHANGE)
    await bid(client, rfq, world.a, 900)
    await bid(client, rfq, world.b, 1000)
    clock.set(at(17, 57))
    keeps_order = await bid(client, rfq, world.b, 950)  # still L2: no extension
    assert keeps_order.json()["extended"] is False

    clock.set(at(17, 58))  # "Supplier B underbids Supplier A at 5:58 PM"
    overtakes = await bid(client, rfq, world.b, 850)
    assert overtakes.json()["extended"] is True
    assert overtakes.json()["current_close_at"].startswith("2026-11-21T18:05")


async def test_l1_change_trigger(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.L1_RANK_CHANGE)
    await bid(client, rfq, world.a, 800)
    await bid(client, rfq, world.b, 900)
    await bid(client, rfq, world.c, 1000)
    clock.set(at(17, 58))
    below_l1 = await bid(client, rfq, world.c, 850)  # L3 -> L2 only
    assert below_l1.json()["extended"] is False

    clock.set(at(17, 59))  # "Supplier C becomes the new lowest bidder at 5:59 PM"
    new_l1 = await bid(client, rfq, world.c, 750)
    assert new_l1.json()["extended"] is True and new_l1.json()["rank"] == 1


async def test_trigger_window_moves_with_each_extension(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.BID_RECEIVED)
    clock.set(at(17, 55))
    await bid(client, rfq, world.a, 1000)  # 6:00 -> 6:05
    clock.set(at(18, 1))  # after the original close, inside the new window 5:55-6:05
    response = await bid(client, rfq, world.b, 990)
    assert response.status_code == 201
    assert response.json()["current_close_at"].startswith("2026-11-21T18:10")


async def test_extensions_never_go_past_forced_close(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(
        session, world.buyer, close=SIX_PM, forced=at(18, 12), trigger=ExtensionTrigger.BID_RECEIVED
    )
    closes = []
    for minute, supplier, price in [
        (55, world.a, 1000),  # 6:00 -> 6:05
        (59, world.b, 990),  # 6:05 -> 6:10
        (61, world.a, 980),  # 6:10 -> 6:12 (cut short: forced close)
        (63, world.b, 970),  # already at the forced close: no extension
    ]:
        clock.set(at(17, 0) + timedelta(minutes=minute))
        response = await bid(client, rfq, supplier, price)
        assert response.status_code == 201
        closes.append(response.json()["current_close_at"][11:16])
    assert closes == ["18:05", "18:10", "18:12", "18:12"]

    extended = await events_of(session, rfq, EventType.AUCTION_EXTENDED)
    capped = await events_of(session, rfq, EventType.EXTENSION_CAPPED)
    assert [e.details["capped"] for e in extended] == [False, False, True]
    assert extended[-1].details["added_seconds"] == 120.0
    assert len(capped) == 1 and "forced close time" in capped[0].message

    clock.set(at(18, 12))
    assert (await bid(client, rfq, world.c, 900)).status_code == 409


async def test_simultaneous_bids_are_applied_one_at_a_time(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    clock: FakeClock,
) -> None:
    """Without the row lock, concurrent bids would read the same close time and lose extensions."""
    async with session_factory() as session:
        world = await make_users(session, supplier_count=12)
        # A 30-minute window keeps every 5:59 PM bid inside the (moving) window.
        rfq = await make_rfq(
            session,
            world.buyer,
            forced=at(20, 0),
            window=30,
            extension=1,
            trigger=ExtensionTrigger.BID_RECEIVED,
        )
    clock.set(at(17, 59))
    responses = await asyncio.gather(
        *(bid(client, rfq, supplier, 1000 + i) for i, supplier in enumerate(world.suppliers))
    )
    assert [r.status_code for r in responses] == [201] * 12

    async with session_factory() as session:
        stored = await session.get(Rfq, rfq.id)
        assert stored is not None
        assert stored.extension_count == 12
        assert stored.current_close_at == SIX_PM + timedelta(minutes=12)
        extensions = await events_of(session, rfq, EventType.AUCTION_EXTENDED)
        # Each extension starts exactly where the previous one ended: no lost updates.
        for previous, current in itertools.pairwise(extensions):
            assert current.details["old_close_at"] == previous.details["new_close_at"]
