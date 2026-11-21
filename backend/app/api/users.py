from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import User
from app.schemas import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut], summary="Users you can act as")
async def list_users(session: SessionDep) -> list[User]:
    result = await session.scalars(select(User).order_by(User.role, User.company))
    return list(result.all())
