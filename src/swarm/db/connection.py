import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
import structlog

logger = structlog.get_logger()


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pool: list[aiosqlite.Connection] = []
        self._max_connections = 10
        self._lock = aiosqlite

    async def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await self._apply_schema(db)
            await db.commit()

        logger.info("database_initialized", db_path=self.db_path)

    async def _apply_schema(self, db: aiosqlite.Connection) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            schema = schema_path.read_text()
            await db.executescript(schema)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def execute(self, query: str, params: tuple = ()) -> None:
        async with self.acquire() as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def fetch_one(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
        async with self.acquire() as conn:
            async with conn.execute(query, params) as cursor:
                return await cursor.fetchone()

    async def fetch_all(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.acquire() as conn:
            async with conn.execute(query, params) as cursor:
                return list(await cursor.fetchall())

    async def fetch_val(self, query: str, params: tuple = ()) -> any:
        row = await self.fetch_one(query, params)
        return row[0] if row else None

    async def close(self) -> None:
        logger.info("database_closed", db_path=self.db_path)
