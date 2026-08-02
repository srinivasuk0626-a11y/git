from __future__ import annotations

from abc import ABC, abstractmethod

from resolveai.domain.models import PolicyDocument, SearchHit


class PolicyRetriever(ABC):
    @abstractmethod
    async def search(self, query: str, *, department: str, top_k: int) -> list[SearchHit]:
        raise NotImplementedError

    @abstractmethod
    async def index(self, documents: list[PolicyDocument]) -> int:
        raise NotImplementedError

    async def close(self) -> None:
        return None
