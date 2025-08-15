from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  source TEXT,
  hash TEXT NOT NULL UNIQUE,
  mp3_path TEXT NOT NULL,
  duration_sec INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hash ON episodes(hash);
"""


class DB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            self.conn = None

    def add_episode(
        self,
        title: str,
        source: str,
        mp3_path: Path,
        duration_sec: int,
        content_bytes: bytes,
    ) -> int:
        h = hashlib.sha256(content_bytes).hexdigest()
        now = int(time.time())
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO episodes (title, created_at, source, hash, mp3_path, duration_sec) VALUES (?, ?, ?, ?, ?, ?);",
            (title, now, source, h, str(mp3_path), duration_sec),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_episodes(self):
        cur = self.conn.execute(
            "SELECT id, title, created_at, source, hash, mp3_path, duration_sec FROM episodes ORDER BY created_at ASC;"
        )
        return cur.fetchall()
