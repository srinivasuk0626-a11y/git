from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from resolveai.domain.models import TicketRecord


class TicketService:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    requester_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    async def create(
        self,
        *,
        idempotency_key: str,
        requester_id: str,
        category: str,
        summary: str,
    ) -> tuple[TicketRecord, bool]:
        return await asyncio.to_thread(
            self._create_sync,
            idempotency_key,
            requester_id,
            category,
            summary,
        )

    def _create_sync(
        self,
        idempotency_key: str,
        requester_id: str,
        category: str,
        summary: str,
    ) -> tuple[TicketRecord, bool]:
        now = datetime.now(UTC)
        with sqlite3.connect(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                "SELECT * FROM tickets WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return self._from_row(existing), False

            ticket_id = f"INC-{uuid4().hex[:10].upper()}"
            connection.execute(
                """
                INSERT INTO tickets (
                    ticket_id, idempotency_key, requester_id, category, summary, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    idempotency_key,
                    requester_id,
                    category,
                    summary,
                    "open",
                    now.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
            assert row is not None
            return self._from_row(row), True

    @staticmethod
    def _from_row(row: sqlite3.Row) -> TicketRecord:
        return TicketRecord(
            ticket_id=row["ticket_id"],
            idempotency_key=row["idempotency_key"],
            requester_id=row["requester_id"],
            category=row["category"],
            summary=row["summary"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
