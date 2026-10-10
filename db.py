"""SQLite storage. Only encrypted data ever touches the disk."""
import sqlite3
from contextlib import closing
from datetime import datetime

import config


def _connect():
    return sqlite3.connect(config.DB_PATH)


def init_db() -> None:
    with closing(_connect()) as con, con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS entries (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   label TEXT NOT NULL UNIQUE COLLATE NOCASE,
                   encrypted_password BLOB NOT NULL,
                   created_at TEXT NOT NULL
               )"""
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value BLOB NOT NULL)"
        )


def get_meta(key: str):
    with closing(_connect()) as con:
        row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(key: str, value: bytes) -> None:
    with closing(_connect()) as con, con:
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def label_exists(label: str) -> bool:
    with closing(_connect()) as con:
        return con.execute("SELECT 1 FROM entries WHERE label = ?", (label,)).fetchone() is not None


def save_entry(label: str, encrypted: bytes) -> None:
    """Insert, or overwrite if the label already exists."""
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as con, con:
        con.execute(
            """INSERT INTO entries (label, encrypted_password, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(label) DO UPDATE SET
                   encrypted_password = excluded.encrypted_password,
                   created_at = excluded.created_at""",
            (label, encrypted, now),
        )


def list_labels() -> list[str]:
    with closing(_connect()) as con:
        rows = con.execute("SELECT label FROM entries ORDER BY label COLLATE NOCASE").fetchall()
    return [r[0] for r in rows]


def get_encrypted(label: str):
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT encrypted_password FROM entries WHERE label = ?", (label,)
        ).fetchone()
    return row[0] if row else None


def delete_entry(label: str) -> None:
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM entries WHERE label = ?", (label,))
