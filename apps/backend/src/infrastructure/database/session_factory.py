"""
Database session factory for the application.

Creates and manages database sessions for repository classes.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import QueuePool
import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager


class DatabaseSessionFactory:
    """Database session factory singleton."""
    
    _instance = None
    _engine = None
    _async_session = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self):
        """Initialize the database engine and session factory."""
        if self._engine is None:
            # Get database URL from environment or use default
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:your-postgres-password@localhost:5432/acmg_ps3"
            )
            
            # Create async engine with connection pooling
            self._engine = create_async_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False  # Set to True for SQL debugging
            )
            
            # Create async session factory
            self._async_session = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
    
    def get_session(self) -> AsyncSession:
        """Get a new database session."""
        if self._async_session is None:
            self.initialize()  # Auto-initialize if not done yet
        return self._async_session()
    
    @asynccontextmanager
    async def get_session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup."""
        async with self.get_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._async_session = None
            self._instance = None


# Global database session factory instance
db_session_factory = DatabaseSessionFactory()


def get_db_session() -> AsyncSession:
    """Get a database session from the factory."""
    return db_session_factory.get_session()


async def initialize_db():
    """Initialize the database session factory."""
    db_session_factory.initialize()


async def close_db():
    """Close the database session factory."""
    await db_session_factory.close()