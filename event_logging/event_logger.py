import os
import json
import sqlite3
from datetime import datetime, timezone


class EventLogger:
    """Logs all OpenChief events to SQLite + JSONL sidecar."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("LOG_DB_PATH", "./logs/openchief.db")
        self.jsonl_path = self.db_path.replace(".db", ".jsonl")
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def log_event(self, event_type: str, data: dict):
        timestamp = datetime.now(timezone.utc).isoformat()
        record = {"timestamp": timestamp, "event_type": event_type, "data": data}

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO events (timestamp, event_type, data) VALUES (?, ?, ?)",
            (timestamp, event_type, json.dumps(data))
        )
        conn.commit()
        conn.close()

        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_recent(self, limit: int = 50, event_type: str = None) -> list:
        conn = sqlite3.connect(self.db_path)
        if event_type:
            rows = conn.execute(
                "SELECT timestamp, event_type, data FROM events WHERE event_type=? ORDER BY id DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT timestamp, event_type, data FROM events ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [{"timestamp": r[0], "event_type": r[1], "data": json.loads(r[2])} for r in rows]
