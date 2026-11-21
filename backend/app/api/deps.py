from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, utcnow
from app.db import get_session
from app.errors import AuthenticationError
from app.models import User
from app.realtime import EventPublisher, NullPublisher

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_clock() -> Clock:
    return utcnow


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_publisher(request: Request) -> EventPublisher:
    return getattr(request.app.state, "publisher", None) or NullPublisher()


PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]


async def get_current_user(
    session: SessionDep, x_user_id: Annotated[str | None, Header()] = None
) -> User:
    if not x_user_id:
        raise AuthenticationError("Choose who you are acting as (X-User-Id header is missing)")
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise AuthenticationError("X-User-Id must be a valid user id") from None
    user = await session.get(User, user_id)
    if user is None:
        raise AuthenticationError("Unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
