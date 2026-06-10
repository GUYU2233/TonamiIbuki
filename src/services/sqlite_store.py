import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from config.settings import settings


class SQLiteStore:
    def __init__(self) -> None:
        self.db_path = settings.SQLITE_DB_PATH
        self.init()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnosis_sessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def upsert_case(self, case_id: str, status: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO cases(case_id, payload, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    payload=excluded.payload,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (case_id, json.dumps(payload, ensure_ascii=False), status, payload.get("created_at", now), now),
            )

    def list_cases(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM cases ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def upsert_session(self, session_id: str, state: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO diagnosis_sessions(session_id, state, payload, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state=excluded.state,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (session_id, state, json.dumps(payload, ensure_ascii=False), payload.get("created_at", now), now),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM diagnosis_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_sessions(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM diagnosis_sessions ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def record_approval(self, session_id: str, operator: str, approved: bool, comment: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO approvals(session_id, operator, approved, comment, created_at) VALUES(?, ?, ?, ?, ?)",
                (session_id, operator, int(approved), comment, datetime.now(timezone.utc).isoformat()),
            )

    def list_approvals(self, session_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if session_id:
                rows = conn.execute("SELECT * FROM approvals WHERE session_id = ? ORDER BY created_at DESC", (session_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


sqlite_store = SQLiteStore()
