"""Database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def get_database_url() -> str:
    """Get the database URL, ensuring the directory exists."""
    # Use configured path if it exists or is writable, otherwise use local ./config
    config_path = settings.config_path
    if not config_path.exists():
        try:
            config_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Fall back to local directory for development
            config_path = Path("./config")
            config_path.mkdir(parents=True, exist_ok=True)

    db_path = config_path / "printarr.db"
    return f"sqlite+aiosqlite:///{db_path}"


# Create async engine
engine = create_async_engine(
    get_database_url(),
    echo=settings.debug,
    future=True,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions.

    Yields:
        An async database session.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
