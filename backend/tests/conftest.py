import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.core.config import Settings, get_settings
from mkvip.db.base import Base
from mkvip.db.session import get_session
from mkvip.main import app


@pytest.fixture
def trusted_origin_headers() -> dict[str, str]:
    return {"Origin": "http://localhost:5173"}


@pytest.fixture
def database_client(
    tmp_path,
    request: pytest.FixtureRequest,
) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'mkvip.db'}"
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
