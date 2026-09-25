"""
PERCEPTA Defense — Database Package.

Provides:
- Base declarative class
- All ORM models (new normalized schema + legacy EventLogModel)
- Async engine, session factory, and dependency injection
"""
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


# ─────────────────────────────────────────────
# Declarative Base
# ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# New normalized schema models
# ─────────────────────────────────────────────
from backend.database.schema import (  # noqa: E402
    Alert,
    AIQuery,
    Camera,
    CameraTransition,
    Detection,
    Evidence,
    Event,
    FaceObservation,
    GlobalEntity,
    Incident,
    LocalTrack,
    PlateObservation,
    Session,
    ThreatAssessment,
    WeaponObservation,
    Zone,
    SyncOutbox,
)

# ─────────────────────────────────────────────
# Legacy model — kept for backward compatibility
# ─────────────────────────────────────────────
from backend.incidents.models import EventLogModel  # noqa: E402


# ─────────────────────────────────────────────
# Async Engine & Session Factory
# ─────────────────────────────────────────────
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str | None = None) -> AsyncEngine:
    """Initialize database engine with WAL mode and create all tables."""
    global _engine, _async_session_factory
    settings = get_settings()
    db_url = database_url or settings.DATABASE_URL

    is_sqlite = "sqlite" in db_url.lower()
    engine_kwargs: dict = {"echo": False, "future": True}
    if not is_sqlite or ":memory:" not in db_url.lower():
        engine_kwargs.update({
            "pool_size": 30,
            "max_overflow": 50,
            "pool_timeout": 60.0,
        })

    _engine = create_async_engine(db_url, **engine_kwargs)

    async with _engine.begin() as conn:
        if is_sqlite:
            try:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA busy_timeout=5000;"))
                await conn.execute(text("PRAGMA synchronous=NORMAL;"))
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the current async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        raise RuntimeError(
            "Database must be initialized via init_db() before obtaining sessions"
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    global _async_session_factory
    if _async_session_factory is None:
        await init_db()
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Gracefully dispose database engine connections."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


__all__ = [
    # Base
    "Base",
    # New normalized models
    "Alert",
    "AIQuery",
    "Camera",
    "CameraTransition",
    "Detection",
    "Evidence",
    "Event",
    "FaceObservation",
    "GlobalEntity",
    "Incident",
    "LocalTrack",
    "PlateObservation",
    "Session",
    "ThreatAssessment",
    "WeaponObservation",
    "Zone",
    "SyncOutbox",
    # Legacy
    "EventLogModel",
    # Engine/session management
    "init_db",
    "get_session_factory",
    "get_db_session",
    "close_db",
]
