from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import simulator
from app.auction import service
from app.enums import ExtensionTrigger
from app.models import Rfq
from tests.helpers import (
    FakeClock,
    RecordingLauncher,
    RecordingPublisher,
    World,
    as_user,
    at,
    make_rfq,
    quote,
)


async def test_metrics_compare_extended_and_non_extended_auctions(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    quiet = await make_rfq(session, world.buyer, name="Quiet")
    busy = await make_rfq(
        session, world.buyer, name="Busy", trigger=ExtensionTrigger.L1_RANK_CHANGE
    )
    for rfq, supplier, total in [
        (quiet, world.a, 1000),
        (quiet, world.b, 950),
        (busy, world.a, 2000),
    ]:
        await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(total), headers=as_user(supplier))
    clock.set(at(17, 56))
    await client.post(f"/api/rfqs/{busy.id}/bids", json=quote(1900), headers=as_user(world.b))
    await client.post(f"/api/rfqs/{busy.id}/bids", json=quote(1800), headers=as_user(world.c))

    clock.set(at(19, 0))
    metrics = (await client.get("/api/metrics", headers=as_user(world.buyer))).json()
    summary = metrics["summary"]
    assert summary["total_auctions"] == 2 and summary["ended_auctions"] == 2
    assert summary["total_bids"] == 5 and summary["avg_bids_per_rfq"] == 2.5
    assert summary["extended_share_pct"] == 50.0
    assert summary["late_bid_share_pct"] == 40.0  # 2 of the 5 bids came in the last X minutes
    assert metrics["extended"] == {
        "auctions": 1,
        "avg_bids_per_rfq": 3.0,
        "avg_suppliers_per_rfq": 3.0,
        "avg_price_improvement_pct": 10.0,  # 2000 -> 1800
    }
    assert metrics["not_extended"]["avg_price_improvement_pct"] == 5.0  # 1000 -> 950


async def test_metrics_are_for_buyers(client: AsyncClient, world: World) -> None:
    assert (await client.get("/api/metrics", headers=as_user(world.a))).status_code == 403


async def test_launch_demo_auction_starts_bots(
    client: AsyncClient, world: World, bot_launcher: RecordingLauncher
) -> None:
    response = await client.post(
        "/api/demo/auctions",
        json={"extension_trigger": "ANY_RANK_CHANGE"},
        headers=as_user(world.buyer),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["bots_started"] is True and body["rfq"]["status"] == "ACTIVE"
    assert [str(rfq_id) for rfq_id in bot_launcher.launched] == [body["rfq"]["id"]]


async def test_bots_bid_until_the_auction_ends(
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    world: World,
    clock: FakeClock,
) -> None:
    rfq = await make_rfq(
        session,
        world.buyer,
        start=at(17, 0),
        close=at(17, 3),
        forced=at(17, 7),
        window=2,
        extension=1,
        trigger=ExtensionTrigger.L1_RANK_CHANGE,
    )

    async def fast_forward(seconds: float) -> None:
        clock.advance(seconds=seconds)

    publisher = RecordingPublisher()
    placed = await simulator.run_bots(
        session_factory, rfq.id, publisher=publisher, seed=7, clock=clock, sleep=fast_forward
    )

    async with session_factory() as fresh:
        stored = await fresh.get(Rfq, rfq.id)
        assert stored is not None
        assert placed > 0 and len(publisher.messages) == placed
        assert clock() >= stored.current_close_at  # the bots stopped because bidding ended
        assert stored.current_close_at <= stored.forced_close_at
        assert (
            stored.current_close_at - stored.bid_close_at
            == timedelta(minutes=stored.extension_count)
            or stored.current_close_at == stored.forced_close_at
        )
        closed = await service.close_due_auctions(fresh, now=clock())
        assert [item.rfq.id for item in closed] == [rfq.id]
