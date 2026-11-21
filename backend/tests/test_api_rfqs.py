import json
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuctionStatus, ExtensionTrigger
from app.errors import PermissionDeniedError
from tests.helpers import SIX_PM, FakeClock, World, as_user, at, make_rfq, quote


def rfq_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "FCL 40' HC Shanghai to Nhava Sheva",
        "origin": "Shanghai",
        "destination": "Nhava Sheva",
        "pickup_date": "2026-12-10",
        "bid_start_at": at(17, 0).isoformat(),
        "bid_close_at": SIX_PM.isoformat(),
        "forced_close_at": at(18, 30).isoformat(),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "L1_RANK_CHANGE",
    }
    payload.update(overrides)
    return payload


async def test_buyer_creates_rfq_with_british_auction_config(
    client: AsyncClient, world: World
) -> None:
    response = await client.post("/api/rfqs", json=rfq_payload(), headers=as_user(world.buyer))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reference_id"] == "RFQ-2026-0001"
    assert body["status"] == "ACTIVE"
    assert body["current_close_at"] == body["bid_close_at"]
    assert body["config"] == {
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
        "extension_trigger": "L1_RANK_CHANGE",
    }
    assert [e["event_type"] for e in body["events"]] == ["RFQ_CREATED"]


async def test_forced_close_must_be_later_than_bid_close(client: AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/rfqs",
        json=rfq_payload(forced_close_at=SIX_PM.isoformat()),
        headers=as_user(world.buyer),
    )
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"][-1] == "forced_close_at"
    assert "later than the bid close time" in error["msg"]


async def test_bid_close_must_be_after_start_and_in_the_future(
    client: AsyncClient, world: World, clock: FakeClock
) -> None:
    before_start = await client.post(
        "/api/rfqs",
        json=rfq_payload(bid_close_at=at(16, 0).isoformat()),
        headers=as_user(world.buyer),
    )
    assert before_start.json()["detail"][0]["loc"][-1] == "bid_close_at"

    clock.set(at(19, 0))  # the 6:00 PM close is now in the past
    in_past = await client.post("/api/rfqs", json=rfq_payload(), headers=as_user(world.buyer))
    assert in_past.status_code == 422
    assert in_past.json()["detail"][0]["loc"][-1] == "bid_close_at"


async def test_custom_reference_ids_must_be_unique(client: AsyncClient, world: World) -> None:
    first = await client.post(
        "/api/rfqs", json=rfq_payload(reference_id="ACME-001"), headers=as_user(world.buyer)
    )
    assert first.json()["reference_id"] == "ACME-001"
    second = await client.post(
        "/api/rfqs", json=rfq_payload(reference_id="ACME-001"), headers=as_user(world.buyer)
    )
    assert second.status_code == 422
    assert second.json()["detail"][0]["loc"][-1] == "reference_id"


async def test_only_buyers_create_rfqs_and_a_user_is_required(
    client: AsyncClient, world: World
) -> None:
    as_supplier = await client.post("/api/rfqs", json=rfq_payload(), headers=as_user(world.a))
    assert as_supplier.status_code == 403
    anonymous = await client.get("/api/rfqs")
    assert anonymous.status_code == 401


async def test_listing_shows_lowest_bid_close_times_and_status(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer)
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1500), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1400), headers=as_user(world.b))

    rows = (await client.get("/api/rfqs", headers=as_user(world.buyer))).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["reference_id"] == rfq.reference_id
    assert row["lowest_bid"] == "1400.00"
    assert row["current_close_at"] == SIX_PM.isoformat().replace("+00:00", "Z")
    assert row["forced_close_at"] == at(18, 30).isoformat().replace("+00:00", "Z")
    assert row["status"] == "ACTIVE"
    assert row["bid_count"] == 2 and row["supplier_count"] == 2
    assert row["my_rank"] is None

    supplier_rows = (await client.get("/api/rfqs", headers=as_user(world.a))).json()
    assert supplier_rows[0]["my_rank"] == 2


async def test_status_filter_agrees_with_derived_status(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    clock.set(at(19, 0))
    upcoming = await make_rfq(
        session, world.buyer, start=at(20, 0), close=at(21, 0), forced=at(21, 30)
    )
    active = await make_rfq(
        session, world.buyer, start=at(18, 0), close=at(19, 30), forced=at(20, 0)
    )
    closed = await make_rfq(session, world.buyer)  # closed at 6:00 PM
    force_closed = await make_rfq(session, world.buyer, close=at(18, 20), forced=at(18, 30))
    force_closed.current_close_at = force_closed.forced_close_at  # extended up to the cap
    await session.commit()

    expected = {
        AuctionStatus.UPCOMING: upcoming,
        AuctionStatus.ACTIVE: active,
        AuctionStatus.CLOSED: closed,
        AuctionStatus.FORCE_CLOSED: force_closed,
    }
    for status, rfq in expected.items():
        rows = (
            await client.get(
                "/api/rfqs", params={"status": status.value}, headers=as_user(world.buyer)
            )
        ).json()
        assert [(r["id"], r["status"]) for r in rows] == [(str(rfq.id), status.value)]


async def test_buyer_details_show_ranked_bids_config_and_extension_reasons(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.L1_RANK_CHANGE)
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1500), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1450), headers=as_user(world.b))
    clock.set(at(17, 56))
    await client.post(
        f"/api/rfqs/{rfq.id}/bids", json=quote(1400, "CMA CGM"), headers=as_user(world.a)
    )

    body = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.buyer))).json()
    assert [(r["rank"], r["supplier_name"], r["bid"]["total_amount"]) for r in body["ranking"]] == [
        (1, world.a.company, "1400.00"),
        (2, world.b.company, "1450.00"),
    ]
    assert [b["total_amount"] for b in body["bids"]] == ["1400.00", "1450.00", "1500.00"]
    assert [b["is_best"] for b in body["bids"]] == [True, True, False]
    first = body["bids"][0]
    assert first["carrier_name"] == "CMA CGM"
    assert first["freight_charges"] == "1120.00" and first["quote_validity_date"] == "2026-12-31"
    assert body["current_close_at"].startswith("2026-11-21T18:05")
    extension = next(e for e in body["events"] if e["event_type"] == "AUCTION_EXTENDED")
    assert extension["message"] == (
        f"Auction extended by 5 min: {world.a.company} replaced {world.b.company} "
        "as L1 within the last 10 min."
    )
    assert body["can_bid"] is False and body["can_award"] is False


async def test_supplier_details_hide_competitors(
    client: AsyncClient, session: AsyncSession, world: World, clock: FakeClock
) -> None:
    rfq = await make_rfq(session, world.buyer, trigger=ExtensionTrigger.ANY_RANK_CHANGE)
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1500), headers=as_user(world.a))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1450), headers=as_user(world.b))
    clock.set(at(17, 58))
    await client.post(f"/api/rfqs/{rfq.id}/bids", json=quote(1420), headers=as_user(world.c))

    body = (await client.get(f"/api/rfqs/{rfq.id}", headers=as_user(world.b))).json()
    assert body["ranking"] == []
    assert [b["supplier_id"] for b in body["bids"]] == [str(world.b.id)]
    position = body["my_position"]
    assert position["rank"] == 2 and position["total_suppliers"] == 3
    assert position["l1_total"] == "1420.00" and position["gap_to_l1"] == "30.00"
    assert body["can_bid"] is True

    visible = json.dumps(body["events"])
    assert world.a.company not in visible and world.c.company not in visible
    assert "1500.00" not in visible  # a competitor's price that is not the L1 price


async def test_unknown_rfq_is_404(client: AsyncClient, world: World) -> None:
    response = await client.get(f"/api/rfqs/{world.buyer.id}", headers=as_user(world.buyer))
    assert response.status_code == 404


async def test_service_rejects_creation_by_supplier(session: AsyncSession, world: World) -> None:
    rfq = await make_rfq(session, world.buyer)
    assert rfq.current_close_at == rfq.bid_close_at
    assert rfq.forced_close_at - rfq.bid_close_at == timedelta(minutes=30)
    with pytest.raises(PermissionDeniedError):
        await make_rfq(session, world.a)
