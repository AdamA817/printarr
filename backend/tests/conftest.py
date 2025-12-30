"""Pytest configuration and fixtures."""

import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set config path BEFORE importing app modules
os.environ["PRINTARR_CONFIG_PATH"] = str(Path(__file__).parent / "test_config")

from app.db import get_db
from app.db.base import Base
from app.main import app

# Create test database engine
TEST_DB_PATH = Path(__file__).parent / "test_config" / "test_printarr.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    # Ensure test config directory exists
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing test database
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="function")
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(test_engine):
    """Create a test client for the FastAPI application with test database."""
    # Create a session maker for the test engine
    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with test_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Override the dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up override
    app.dependency_overrides.clear()
