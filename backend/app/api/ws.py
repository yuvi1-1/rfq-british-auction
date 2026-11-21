from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime import ConnectionManager

router = APIRouter(tags=["live updates"])


async def _serve(websocket: WebSocket, rfq_id: str | None) -> None:
    manager: ConnectionManager = websocket.app.state.ws_manager
    await manager.connect(websocket, rfq_id)
    try:
        while True:
            # Clients send periodic pings; we only read to notice disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/ws/rfqs")
async def all_auction_updates(websocket: WebSocket) -> None:
    """Every auction change (used by the listing page and toasts)."""
    await _serve(websocket, None)


@router.websocket("/ws/rfqs/{rfq_id}")
async def auction_updates(websocket: WebSocket, rfq_id: str) -> None:
    """Changes to a single auction."""
    await _serve(websocket, rfq_id)
