"""Create the pgvector extension and all tables.

For a take-home-scale project we use `create_all` instead of a full Alembic
migration chain — documented as a deliberate scope trade-off in the PRD.
A production deployment should replace this with Alembic migrations.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models import db_models  # noqa: E402,F401  (import registers models on Base.metadata)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized: extension + tables ready.")


if __name__ == "__main__":
    asyncio.run(main())
