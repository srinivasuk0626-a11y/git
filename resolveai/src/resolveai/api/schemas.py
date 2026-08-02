from __future__ import annotations

from pydantic import BaseModel, Field

from resolveai.domain.enums import ApprovalDecision
from resolveai.domain.models import ServiceRequest


class CreateRequestBody(ServiceRequest):
    pass


class ApprovalBody(BaseModel):
    decision: ApprovalDecision
    reviewer_id: str = Field(min_length=3, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)
