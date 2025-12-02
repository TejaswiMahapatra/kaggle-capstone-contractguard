"""
PostgreSQL Database Connection and Session Management

Provides async database connectivity for:
- User management
- Document metadata storage
- Session persistence
- Audit logging

Uses SQLAlchemy 2.0 async patterns for high performance.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__, component="database")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# Build database URL
def _get_database_url() -> str:
    """Construct database URL from settings."""
    if hasattr(settings, 'database_url') and settings.database_url:
        return settings.database_url

    # Build from components
    user = getattr(settings, 'postgres_user', 'postgres')
    password = getattr(settings, 'postgres_password', 'postgres')
    host = getattr(settings, 'postgres_host', 'localhost')
    port = getattr(settings, 'postgres_port', 5432)
    db = getattr(settings, 'postgres_db', 'contractguard')

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


# Create async engine
_engine = None
_async_session_maker = None


def _get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        database_url = _get_database_url()
        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
            future=True,
            pool_pre_ping=True,
            poolclass=NullPool if settings.app_env == "development" else None,
        )
        logger.info("Database engine created", url=database_url.split("@")[-1])
    return _engine


def _get_session_maker():
    """Get or create async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = _get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_db_session():
    """
    Get a database session for use in background workers.

    Usage:
        async with get_db_session() as db:
            result = await db.execute(select(User))
    """
    return _get_session_maker()()


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in models.
    NOTE: In production, use Alembic migrations instead.
    """
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections gracefully."""
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
    logger.info("Database connections closed")


async def check_db_health() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        session_maker = _get_session_maker()
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False
