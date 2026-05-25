import asyncpg
import logging
import os
from typing import Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            try:
                # Explicitly unset PGPORT and other PG environment variables 
                # that might contain user-pasted passwords or incorrect values
                for env_var in ["PGPORT", "PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"]:
                    if env_var in os.environ:
                        val = os.environ[env_var]
                        # If the value is not numeric for a port, or looks like a password
                        if env_var == "PGPORT" and not val.isdigit():
                            logger.warning(f"Unsetting invalid {env_var}='{val}'")
                            os.environ.pop(env_var)

                # Some platforms provide postgres:// but asyncpg prefers postgresql://
                dsn = settings.DATABASE_URL
                if dsn.startswith("postgres://"):
                    dsn = dsn.replace("postgres://", "postgresql://", 1)
                
                # Remove query parameters that might cause "bad query field" errors
                # Supabase/Render strings sometimes include unsupported params for asyncpg
                if "?" in dsn:
                    base_dsn, query = dsn.split("?", 1)
                    # Keep only known safe params if needed, or just use base_dsn
                    # For now, let's try the base_dsn if it has unsupported fields
                    # but usually sslmode is what people want. 
                    # asyncpg uses 'ssl' instead of 'sslmode'
                    dsn = base_dsn

                cls._pool = await asyncpg.create_pool(
                    dsn,
                    min_size=5,
                    max_size=20,
                    statement_cache_size=0,
                    command_timeout=60,
                    ssl='require' if "supabase" in dsn or "render" in dsn else None
                )
                logger.info("Database connection pool created.")
            except Exception as e:
                # Log a redacted version of the URL for debugging
                redacted_url = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "URL hidden"
                logger.error(f"Failed to create database pool for host: {redacted_url}. Error: {e}")
                raise
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed.")

    @classmethod
    async def execute(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def fetchrow(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetchval(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
