from fastapi import APIRouter

from app.api.deps import ClockDep, CurrentUser, SessionDep
from app.auction import queries
from app.enums import UserRole
from app.errors import PermissionDeniedError
from app.schemas import MetricsOut

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics", response_model=MetricsOut, summary="Success metrics (buyers)")
async def get_metrics(session: SessionDep, user: CurrentUser, clock: ClockDep) -> MetricsOut:
    if user.role != UserRole.BUYER:
        raise PermissionDeniedError("Metrics are only available to buyers")
    return await queries.compute_metrics(session, clock())
