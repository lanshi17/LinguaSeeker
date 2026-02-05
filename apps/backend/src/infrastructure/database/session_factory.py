"""
Database session factory for the application.

Creates and manages database sessions for repository classes.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from urllib.parse import quote_plus


class DatabaseSessionFactory:
    """Database session factory singleton."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engine = None
            cls._instance._session_maker = None
            cls._instance._database_url = None
        return cls._instance

    def _ensure_env_loaded(self):
        """Ensure environment variables are loaded."""
        import os
        from dotenv import load_dotenv
        from pathlib import Path

        # Only load if not already loaded (check for a common variable)
        if not os.getenv('POSTGRES_USER'):
            # Load .env file first
            load_dotenv('.env', override=False)

            # Then load environment-specific file
            env_name = os.getenv('ENVIRONMENT', 'development').lower()
            env_path = Path(f'.env.{env_name}')
            if env_path.exists():
                load_dotenv(env_path, override=True)

            # Finally, load specific ENV_FILE if provided
            env_file = os.getenv('ENV_FILE')
            if env_file:
                env_file_path = Path(env_file)
                if env_file_path.exists():
                    load_dotenv(env_file_path, override=True)

    def _build_database_url(self) -> str:
        """Build the DATABASE_URL from current environment values."""
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "your-postgres-password")
        encoded_password = quote_plus(password) if password else ""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "acmg_ps3")

        return os.getenv(
            "DATABASE_URL",
            f"postgresql+asyncpg://{user}:{encoded_password}@{host}:{port}/{database}",
        )

    def _ensure_engine(self) -> None:
        """Create (or reuse) the AsyncEngine/session maker."""
        database_url = self._build_database_url()
        if self._engine and database_url == self._database_url:
            return

        if self._engine and database_url != self._database_url:
            # Database target changed; dispose old engine before replacing.
            # Disposal is async, so we schedule it via loop when possible.
            import asyncio

            old_engine = self._engine

            async def _dispose(engine):
                await engine.dispose()

            try:
                asyncio.get_running_loop().create_task(_dispose(old_engine))
            except RuntimeError:
                asyncio.run(_dispose(old_engine))

        self._engine = create_async_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False,
        )
        self._session_maker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._database_url = database_url

    def get_session(self) -> AsyncSession:
        """Get a pooled AsyncSession."""
        self._ensure_env_loaded()
        self._ensure_engine()
        return self._session_maker()

    @asynccontextmanager
    async def get_session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup and error handling."""
        session = self.get_session()
        try:
            yield session
        except Exception as e:
            try:
                await session.rollback()
            except Exception:
                logging.exception("Failed to rollback session after error")
            logging.error(f"Database session error, transaction rolled back: {e}")
            raise
        finally:
            await session.close()

    async def close(self):
        """Close any resources if needed."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            self._database_url = None


# Global database session factory instance
db_session_factory = DatabaseSessionFactory()


def get_db_session() -> AsyncSession:
    """Get a database session from the factory.

    Note: This returns a raw session. For proper transaction management,
    use get_session_context() as a context manager instead.
    """
    return db_session_factory.get_session()


async def initialize_db():
    """Initialize the database session factory."""
    # This is now a no-op since we create engines dynamically
    pass


async def close_db():
    """Close the database session factory."""
    # This is now a no-op
    pass
