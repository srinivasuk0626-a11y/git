from __future__ import annotations

from resolveai.domain.models import IdentityRecord


class IdentityNotFoundError(LookupError):
    pass


class IdentityService:
    def __init__(self, identities: list[IdentityRecord]) -> None:
        self._identities = {identity.user_id: identity for identity in identities}

    async def get(self, user_id: str) -> IdentityRecord:
        try:
            return self._identities[user_id]
        except KeyError as exc:
            raise IdentityNotFoundError(f"Identity {user_id!r} was not found") from exc
