from __future__ import annotations

from typing import Any, TypedDict


class ResolutionState(TypedDict, total=False):
    thread_id: str
    request: dict[str, Any]
    status: str
    started_at: float
    completed_at: float
    request_type: str
    guardrail_reasons: list[str]
    identity: dict[str, Any] | None
    policy_hits: list[dict[str, Any]]
    warnings: list[str]
    plan: dict[str, Any]
    approval: dict[str, Any] | None
    ticket: dict[str, Any] | None
    message: str
    metrics: dict[str, Any]
