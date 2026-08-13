from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TeachLoopStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS teacher_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    teacher_note TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_version(
        self,
        title: str,
        status: str,
        payload: dict[str, Any],
        teacher_note: str = "",
    ) -> int:
        created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO teacher_versions (title, status, teacher_note, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, status, teacher_note, json.dumps(payload, ensure_ascii=False), created_at),
            )
            return int(cursor.lastrowid)

    def list_versions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, status, teacher_note, payload_json, created_at
                FROM teacher_versions ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "status": row["status"],
                "teacher_note": row["teacher_note"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_feedback(self, lesson_title: str, payload: dict[str, Any]) -> int:
        created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO feedback_runs (lesson_title, payload_json, created_at)
                VALUES (?, ?, ?)
                """,
                (lesson_title, json.dumps(payload, ensure_ascii=False), created_at),
            )
            return int(cursor.lastrowid)

