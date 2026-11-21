from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auction import service
from app.enums import EventType, ExtensionTrigger
from tests.helpers import SIX_PM, FakeClock, World, as_user, at, make_rfq, quote


async def test_close_sweep_finalizes_closed_and_force_closed_auctions(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    normal = await make_rfq(session, world.buyer, name="Closes on time")
    capped = await make_rfq(
        session,
        world.buyer,
        name="Runs into the cap",
        forced=at(18, 3),
        trigger=ExtensionTrigger.BID_RECEIVED,
    )
    running = await make_rfq(
        session, world.buyer, name="Still running", close=at(19, 0), forced=at(19, 30)
    )
    await client.post(f"/api/rfqs/{normal.id}/bids", json=quote(1200), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{normal.id}/bids", json=quote(1100), headers=as_user(world.b))
    clock.set(at(17, 58))
    await client.post(f"/api/rfqs/{capped.id}/bids", json=quote(900), headers=as_user(world.a))

    closed = await service.close_due_auctions(session, now=at(18, 10))
    by_name = {item.rfq.name: item.event for item in closed}
    assert set(by_name) == {"Closes on time", "Runs into the cap"}
    assert by_name["Closes on time"].event_type is EventType.AUCTION_CLOSED
    assert by_name["Closes on time"].occurred_at == SIX_PM
    assert by_name["Closes on time"].message == (
        f"Auction closed. 2 bids from 2 suppliers. Final L1: {world.b.company} at USD 1,100.00."
    )
    assert by_name["Runs into the cap"].event_type is EventType.AUCTION_FORCE_CLOSED
    assert by_name["Runs into the cap"].occurred_at == at(18, 3)

    # Running the sweep again finds nothing new; the running auction is untouched.
    assert await service.close_due_auctions(session, now=at(18, 10)) == []
    await session.refresh(running)
    assert running.closed_at is None

    clock.set(at(18, 10))
    statuses = {
        row["name"]: row["status"]
        for row in (await client.get("/api/rfqs", headers=as_user(world.buyer))).json()
    }
    assert statuses == {
        "Closes on time": "CLOSED",
        "Runs into the cap": "FORCE_CLOSED",
        "Still running": "ACTIVE",
    }


async def test_award_flow(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer)
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1300), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1250), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1280), headers=as_user(world.b))

    detail = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.buyer))).json()
    l1_bid, l2_bid = (row["bid"]["id"] for row in detail["ranking"])
    superseded = next(b["id"] for b in detail["bids"] if not b["is_best"])

    too_early = await client.post(
        f"/api/rfqs/{rfq.id}/award", json={"bid_id": l1_bid}, headers=as_user(world.buyer)
    )
    assert too_early.status_code == 409

    clock.set(at(18, 1))
    assert (
        await client.post(
            f"/api/rfqs/{rfq.id}/award", json={"bid_id": l1_bid}, headers=as_user(world.a)
        )
    ).status_code == 403
    old_quote = await client.post(
        f"/api/rfqs/{rfq.id}/award", json={"bid_id": superseded}, headers=as_user(world.buyer)
    )
    assert old_quote.status_code == 422

    # The buyer may pick any final quote, e.g. L2 for a better transit time.
    awarded = await client.post(
        f"/api/rfqs/{rfq.id}/award", json={"bid_id": l2_bid}, headers=as_user(world.buyer)
    )
    assert awarded.status_code == 200, awarded.text
    body = awarded.json()
    assert body["award"]["supplier_name"] == world.b.company
    assert body["can_award"] is False and body["is_awarded"] is True
    assert body["events"][0]["message"].startswith(f"Awarded to {world.b.company}")

    again = await client.post(
        f"/api/rfqs/{rfq.id}/award", json={"bid_id": l1_bid}, headers=as_user(world.buyer)
    )
    assert again.status_code == 409

    winner = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.b))).json()["award"]
    loser = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.a))).json()["award"]
    assert winner["awarded_to_me"] is True and winner["total_amount"] == "1280.00"
    assert loser["awarded_to_me"] is False and loser["total_amount"] is None
