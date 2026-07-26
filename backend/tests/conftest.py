import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.api.dependencies import get_company_repository, get_current_user
from mkvip.core.config import Settings, get_settings
from mkvip.db.base import Base
from mkvip.db.session import get_session
from mkvip.main import app
from mkvip.repositories.memory import InMemoryCompanyRepository
from mkvip.schemas.auth import UserRead

TEST_USER = UserRead(
    id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
    email="investor@example.com",
    created_at=datetime(2026, 7, 26, tzinfo=UTC),
)


@pytest.fixture
def trusted_origin_headers() -> dict[str, str]:
    return {"Origin": "http://localhost:5173"}


@pytest.fixture
def repository() -> InMemoryCompanyRepository:
    return InMemoryCompanyRepository()


@pytest.fixture
def client(repository: InMemoryCompanyRepository) -> Iterator[TestClient]:
    app.dependency_overrides[get_company_repository] = lambda: repository
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(
        app,
        headers={"Origin": "http://localhost:5173"},
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client() -> Iterator[TestClient]:
    with TestClient(
        app,
        headers={"Origin": "http://localhost:5173"},
    ) as test_client:
        yield test_client


@pytest.fixture
def database_client(
    request: pytest.FixtureRequest,
) -> Iterator[TestClient]:
    database_url = "sqlite+aiosqlite://"
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with factory() as session:
            yield session

    settings_overrides = getattr(request, "param", {})
    settings = Settings(
        database_url=database_url,
        _env_file=None,
        **settings_overrides,
    )
    asyncio.run(prepare_database())
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
