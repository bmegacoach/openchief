"""
SQLite-backed context store: maps channel_id → Agent Zero context_id.
Survives restarts. Shared between openchief (Python) and chief-botsuite (Node.js).
WAL mode enabled for safe concurrent access.
"""
import os, uuid, aiosqlite
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "contexts.db"


def _db_path() -> Path:
    env = os.getenv("CONTEXT_DB_PATH")
    return Path(env) if env else _DEFAULT_DB


async def init_db():
    """Create tables if they don't exist. Call once at bot startup."""
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(p) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contexts (
                channel_id    TEXT PRIMARY KEY,
                a0_context_id TEXT NOT NULL,
                context_type  TEXT DEFAULT 'channel',
                created_at    TEXT NOT NULL,
                last_used     TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                health_pct    REAL    DEFAULT 0.0
            )
        """)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.commit()


async def get_or_create(channel_id: str, context_type: str = "channel") -> str:
    """Return existing a0_context_id or create a new one for channel_id."""
    p = _db_path()
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(p) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT a0_context_id FROM contexts WHERE channel_id=?", (channel_id,)
        )).fetchone()
        if row:
            await db.execute(
                "UPDATE contexts SET last_used=? WHERE channel_id=?", (now, channel_id)
            )
            await db.commit()
            return row["a0_context_id"]
        cid = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO contexts VALUES (?,?,?,?,?,0,0.0)",
            (channel_id, cid, context_type, now, now),
        )
        await db.commit()
        return cid


async def update_health(channel_id: str, message_count: int, health_pct: float):
    """Update fill stats for a context (called by HealthMonitor)."""
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        await db.execute(
            "UPDATE contexts SET message_count=?, health_pct=? WHERE channel_id=?",
            (message_count, health_pct, channel_id),
        )
        await db.commit()


async def all_active() -> list[dict]:
    """Return context rows used in the last 7 days, newest first."""
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute("""
            SELECT * FROM contexts
            WHERE last_used > datetime('now', '-7 days')
            ORDER BY last_used DESC
        """)).fetchall()
        return [dict(r) for r in rows]


async def delete_context(channel_id: str):
    """Remove a context row (used by /reset command)."""
    p = _db_path()
    async with aiosqlite.connect(p) as db:
        await db.execute("DELETE FROM contexts WHERE channel_id=?", (channel_id,))
        await db.commit()


def create_ephemeral(label: str) -> str:
    """Return a one-time context_id for cron jobs. Not persisted in SQLite."""
    return f"ephemeral-{label}-{uuid.uuid4()}"
