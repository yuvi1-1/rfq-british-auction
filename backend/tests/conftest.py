import os
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.demo import get_bot_launcher
from app.api.deps import get_clock, get_publisher
from app.db import get_session
from app.main import app
from tests.helpers import (
    FakeClock,
    RecordingLauncher,
    RecordingPublisher,
    World,
    at,
    make_users,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://rfq:rfq@localhost:5432/rfq_test"
)
BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    conn = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database="postgres",
    )
    try:
        found = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", parsed.database)
        if not found:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await conn.close()


def _migrate(connection: Connection, config: Config) -> None:
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    await _ensure_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(_migrate, config)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async with db_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE auction_events, bids, rfqs, users RESTART IDENTITY CASCADE")
        )
        await conn.execute(text("ALTER SEQUENCE rfq_reference_seq RESTART WITH 1"))
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db_session:
        yield db_session


@pytest.fixture
async def world(session: AsyncSession) -> World:
    return await make_users(session)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(at(17, 0))  # 5:00 PM, an hour before the spec's 6:00 PM close


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def bot_launcher() -> RecordingLauncher:
    return RecordingLauncher()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    clock: FakeClock,
    publisher: RecordingPublisher,
    bot_launcher: RecordingLauncher,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_bot_launcher] = lambda: bot_launcher
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
