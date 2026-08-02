from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


class AuditLedger:
    """Append-only JSONL audit log with a simple hash chain."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            previous_hash = await asyncio.to_thread(self._read_last_hash)
            event = {
                "timestamp": datetime.now(UTC).isoformat(),
                "event_type": event_type,
                "payload": payload,
                "previous_hash": previous_hash,
            }
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
            event["event_hash"] = sha256(canonical.encode("utf-8")).hexdigest()
            await asyncio.to_thread(self._append_sync, event)
            return event

    def _read_last_hash(self) -> str:
        if not self._path.exists() or self._path.stat().st_size == 0:
            return "GENESIS"
        lines = [line for line in self._path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return "GENESIS"
        return str(json.loads(lines[-1])["event_hash"])

    def _append_sync(self, event: dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
