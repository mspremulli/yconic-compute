#!/usr/bin/env python3
"""Initialize SQLite database with schema."""
import asyncio
import aiosqlite
import re
from pathlib import Path


async def init_db(db_path: str = "./data/swarm.db") -> None:
    schema_path = Path(__file__).parent.parent / "src" / "swarm" / "db" / "schema.sql"
    schema = schema_path.read_text()
    
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(db_path) as db:
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                await db.execute(statement)
        await db.commit()
    
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "./data/swarm.db"
    asyncio.run(init_db(db_path))
