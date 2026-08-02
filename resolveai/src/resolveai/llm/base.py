from __future__ import annotations

from abc import ABC, abstractmethod

from resolveai.domain.models import ActionPlan, IdentityRecord, PolicyDocument, ServiceRequest
from resolveai.domain.enums import RequestType


class DecisionEngine(ABC):
    @abstractmethod
    async def classify(self, request: ServiceRequest) -> RequestType:
        raise NotImplementedError

    @abstractmethod
    async def propose_plan(
        self,
        *,
        request: ServiceRequest,
        request_type: RequestType,
        identity: IdentityRecord | None,
        policies: list[PolicyDocument],
        warnings: list[str],
    ) -> ActionPlan:
        raise NotImplementedError

    async def close(self) -> None:
        return None
