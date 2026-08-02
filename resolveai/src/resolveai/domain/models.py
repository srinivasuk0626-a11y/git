from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from resolveai.domain.enums import RequestType, RiskLevel, WorkflowStatus


class ServiceRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    requester_id: str = Field(min_length=3, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    text: str = Field(min_length=5, max_length=8000)
    requested_resource: str | None = Field(default=None, max_length=200)
    business_justification: str | None = Field(default=None, max_length=1000)
    source: str = Field(default="api", max_length=50)

    @field_validator("department")
    @classmethod
    def normalize_department(cls, value: str) -> str:
        return value.lower().replace(" ", "-")


class IdentityRecord(BaseModel):
    user_id: str
    display_name: str
    department: str
    manager_id: str | None = None
    employment_status: str
    entitlements: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    policy_id: str
    policy_key: str
    title: str
    version: int = Field(ge=1)
    department: str
    status: str
    effective_from: date
    expires_at: date | None = None
    content: str
    rules: dict[str, Any] = Field(default_factory=dict)
    source_uri: str
    updated_at: datetime
    suspicious: bool = False

    def is_active(self, today: date | None = None) -> bool:
        today = today or datetime.now(UTC).date()
        return (
            self.status == "active"
            and self.effective_from <= today
            and (self.expires_at is None or self.expires_at >= today)
        )


class SearchHit(BaseModel):
    document: PolicyDocument
    score: float = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)


class ActionPlan(BaseModel):
    request_type: RequestType
    summary: str
    evidence_policy_ids: list[str] = Field(default_factory=list)
    proposed_action: str
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool
    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class TicketRecord(BaseModel):
    ticket_id: str
    idempotency_key: str
    requester_id: str
    category: str
    summary: str
    status: str
    created_at: datetime


class WorkflowResult(BaseModel):
    thread_id: str
    status: WorkflowStatus
    message: str
    request_type: RequestType | None = None
    risk_level: RiskLevel | None = None
    evidence_policy_ids: list[str] = Field(default_factory=list)
    approval_required: bool = False
    ticket: TicketRecord | None = None
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
