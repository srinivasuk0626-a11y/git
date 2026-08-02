from pathlib import Path

import pytest

from resolveai.tools.ticketing import TicketService


@pytest.mark.asyncio
async def test_ticket_creation_is_idempotent(tmp_path: Path) -> None:
    service = TicketService(tmp_path / "tickets.db")
    await service.initialize()
    first, first_created = await service.create(
        idempotency_key="same-key",
        requester_id="usr-1",
        category="incident",
        summary="Pipeline failed",
    )
    second, second_created = await service.create(
        idempotency_key="same-key",
        requester_id="usr-1",
        category="incident",
        summary="Pipeline failed",
    )
    assert first_created is True
    assert second_created is False
    assert first.ticket_id == second.ticket_id
