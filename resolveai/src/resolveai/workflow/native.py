from __future__ import annotations

import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from resolveai.domain.enums import ApprovalDecision, RequestType, WorkflowStatus
from resolveai.domain.models import ActionPlan, ServiceRequest, WorkflowResult
from resolveai.llm.base import DecisionEngine
from resolveai.observability.audit import AuditLedger
from resolveai.observability.metrics import (
    APPROVALS,
    GUARDRAIL_BLOCKS,
    REQUESTS,
    RETRIEVAL_HITS,
    TICKETS,
    WORKFLOW_LATENCY,
)
from resolveai.retrieval.base import PolicyRetriever
from resolveai.security.guardrails import authorize_action, inspect_untrusted_text
from resolveai.tools.identity import IdentityNotFoundError, IdentityService
from resolveai.tools.ticketing import TicketService
from resolveai.workflow.state import ResolutionState


@dataclass(slots=True)
class WorkflowDependencies:
    retriever: PolicyRetriever
    identity_service: IdentityService
    ticket_service: TicketService
    decision_engine: DecisionEngine
    audit_ledger: AuditLedger
    policy_top_k: int = 4


class NativeResolutionWorkflow:
    """Explicit, deterministic state machine used by the API and tests.

    A LangGraph adapter wraps the same transitions in `workflow/langgraph_adapter.py`.
    Keeping the transition logic independent makes it easy to test without a framework.
    """

    def __init__(self, dependencies: WorkflowDependencies) -> None:
        self._deps = dependencies
        self._pending: dict[str, ResolutionState] = {}
        self._completed: dict[str, ResolutionState] = {}

    async def start(self, thread_id: str, request: ServiceRequest) -> WorkflowResult:
        started = time.perf_counter()
        state: ResolutionState = {
            "thread_id": thread_id,
            "request": request.model_dump(mode="json"),
            "status": WorkflowStatus.RECEIVED.value,
            "started_at": started,
            "warnings": [],
            "metrics": {},
        }

        finding = inspect_untrusted_text(request.text)
        if finding.blocked:
            for reason in finding.reasons:
                GUARDRAIL_BLOCKS.labels(reason=reason).inc()
            state.update(
                status=WorkflowStatus.BLOCKED.value,
                guardrail_reasons=finding.reasons,
                message="The request was blocked by input security controls.",
            )
            return await self._finish(state, started)

        request_type = await self._deps.decision_engine.classify(request)
        state["request_type"] = request_type.value

        hits = await self._deps.retriever.search(
            request.text,
            department=request.department,
            top_k=self._deps.policy_top_k,
        )
        RETRIEVAL_HITS.observe(len(hits))
        safe_hits = []
        allowed_policy_keys = {
            RequestType.ACCESS_REQUEST: {"production-access", "privacy-handling", "lead-data-access"},
            RequestType.INCIDENT: {"data-platform-incident", "privacy-handling"},
            RequestType.DATA_QUESTION: {"data-platform-incident", "privacy-handling"},
            RequestType.POLICY_QUESTION: None,
            RequestType.UNKNOWN: None,
        }[request_type]
        for hit in hits:
            if hit.document.suspicious:
                state["warnings"].append("suspicious_policy_quarantined")
                GUARDRAIL_BLOCKS.labels(reason="suspicious_policy_quarantined").inc()
                continue
            if allowed_policy_keys is not None and hit.document.policy_key not in allowed_policy_keys:
                continue
            safe_hits.append(hit)
        state["policy_hits"] = [hit.model_dump(mode="json") for hit in safe_hits]

        active_by_key: dict[str, list[Any]] = {}
        for hit in safe_hits:
            if hit.document.is_active():
                active_by_key.setdefault(hit.document.policy_key, []).append(hit.document)
        for policies in active_by_key.values():
            rule_variants = {str(sorted(policy.rules.items())) for policy in policies}
            if len(policies) > 1 and len(rule_variants) > 1:
                state["warnings"].append("policy_conflict")
                break

        identity = None
        try:
            identity = await self._deps.identity_service.get(request.requester_id)
            state["identity"] = identity.model_dump(mode="json")
        except IdentityNotFoundError:
            state["identity"] = None
            state["warnings"].append("identity_not_found")

        plan = await self._deps.decision_engine.propose_plan(
            request=request,
            request_type=request_type,
            identity=identity,
            policies=[hit.document for hit in safe_hits],
            warnings=state["warnings"],
        )
        plan = self._enforce_invariants(plan, safe_policy_ids={hit.document.policy_id for hit in safe_hits})
        state["plan"] = plan.model_dump(mode="json")

        if identity is not None:
            authorization = authorize_action(
                action=plan.proposed_action,
                risk_flags=identity.risk_flags,
                employment_status=identity.employment_status,
            )
            if authorization.blocked:
                state["warnings"].extend(authorization.reasons)
                state.update(
                    status=WorkflowStatus.ESCALATED.value,
                    message="The action was not authorized and has been escalated for manual review.",
                )
                return await self._finish(state, started)

        if plan.requires_approval:
            state.update(
                status=WorkflowStatus.PENDING_APPROVAL.value,
                message="The proposed state-changing action requires human approval.",
            )
            self._pending[thread_id] = state
            await self._deps.audit_ledger.append(
                "workflow.pending_approval",
                {"thread_id": thread_id, "plan": state["plan"]},
            )
            return self._to_result(state)

        await self._execute(state)
        return await self._finish(state, started)

    async def approve(
        self,
        thread_id: str,
        *,
        decision: ApprovalDecision,
        reviewer_id: str,
        comment: str | None = None,
    ) -> WorkflowResult:
        if thread_id not in self._pending:
            if thread_id in self._completed:
                return self._to_result(self._completed[thread_id])
            raise KeyError(f"No pending workflow with thread_id={thread_id}")

        state = self._pending.pop(thread_id)
        state["approval"] = {
            "decision": decision.value,
            "reviewer_id": reviewer_id,
            "comment": comment,
        }
        APPROVALS.labels(decision=decision.value).inc()
        await self._deps.audit_ledger.append(
            "workflow.approval_decision",
            {"thread_id": thread_id, "approval": state["approval"]},
        )

        if decision == ApprovalDecision.DENY:
            state.update(
                status=WorkflowStatus.DENIED.value,
                message="The proposed action was denied by the reviewer.",
            )
            return await self._finish(state, state["started_at"])

        await self._execute(state)
        return await self._finish(state, state["started_at"])

    async def get(self, thread_id: str) -> WorkflowResult:
        state = self._pending.get(thread_id) or self._completed.get(thread_id)
        if state is None:
            raise KeyError(thread_id)
        return self._to_result(state)

    @staticmethod
    def _enforce_invariants(plan: ActionPlan, *, safe_policy_ids: set[str]) -> ActionPlan:
        evidence = [policy_id for policy_id in plan.evidence_policy_ids if policy_id in safe_policy_ids]
        updates: dict[str, Any] = {"evidence_policy_ids": evidence}

        if plan.proposed_action in {"grant_access", "restore_access"}:
            updates["requires_approval"] = True
        if not evidence and plan.proposed_action in {"grant_access", "restore_access"}:
            updates.update(
                proposed_action="escalate_for_manual_review",
                tool_name="create_service_ticket",
                requires_approval=False,
                unresolved_questions=[
                    *plan.unresolved_questions,
                    "No validated policy evidence supports the requested access change",
                ],
            )
        return plan.model_copy(update=updates)

    async def _execute(self, state: ResolutionState) -> None:
        request = ServiceRequest.model_validate(state["request"])
        plan = ActionPlan.model_validate(state["plan"])

        if plan.tool_name != "create_service_ticket":
            state.update(
                status=WorkflowStatus.COMPLETED.value,
                message=self._evidence_answer(plan),
            )
            return

        idempotency_source = "|".join(
            [
                request.requester_id,
                plan.proposed_action,
                (request.requested_resource or "").lower(),
                (request.business_justification or "").lower(),
                plan.summary.lower(),
            ]
        )
        idempotency_key = sha256(idempotency_source.encode("utf-8")).hexdigest()
        ticket, created = await self._deps.ticket_service.create(
            idempotency_key=idempotency_key,
            requester_id=request.requester_id,
            category=plan.request_type.value,
            summary=plan.summary,
        )
        TICKETS.labels(outcome="created" if created else "reused").inc()
        state["ticket"] = ticket.model_dump(mode="json")
        state.update(
            status=WorkflowStatus.COMPLETED.value,
            message=(
                f"Ticket {ticket.ticket_id} was created and routed for execution."
                if created
                else f"Existing ticket {ticket.ticket_id} was reused; no duplicate was created."
            ),
        )

    @staticmethod
    def _evidence_answer(plan: ActionPlan) -> str:
        evidence = ", ".join(plan.evidence_policy_ids) or "no validated policy"
        return f"Resolution completed using policy evidence: {evidence}."

    async def _finish(self, state: ResolutionState, started: float) -> WorkflowResult:
        duration = max(time.perf_counter() - started, 0.0)
        state["completed_at"] = time.perf_counter()
        state["metrics"] = {
            **state.get("metrics", {}),
            "latency_seconds": round(duration, 6),
            "policy_hits": len(state.get("policy_hits", [])),
        }
        request_type = state.get("request_type", RequestType.UNKNOWN.value)
        REQUESTS.labels(status=state["status"], request_type=request_type).inc()
        WORKFLOW_LATENCY.observe(duration)
        await self._deps.audit_ledger.append(
            "workflow.completed",
            {
                "thread_id": state["thread_id"],
                "status": state["status"],
                "request_type": request_type,
                "warnings": state.get("warnings", []),
                "ticket_id": (state.get("ticket") or {}).get("ticket_id"),
                "latency_seconds": duration,
            },
        )
        self._completed[state["thread_id"]] = state
        return self._to_result(state)

    @staticmethod
    def _to_result(state: ResolutionState) -> WorkflowResult:
        plan = ActionPlan.model_validate(state["plan"]) if state.get("plan") else None
        return WorkflowResult(
            thread_id=state["thread_id"],
            status=WorkflowStatus(state["status"]),
            message=state.get("message", ""),
            request_type=RequestType(state["request_type"]) if state.get("request_type") else None,
            risk_level=plan.risk_level if plan else None,
            evidence_policy_ids=plan.evidence_policy_ids if plan else [],
            approval_required=state["status"] == WorkflowStatus.PENDING_APPROVAL.value,
            ticket=state.get("ticket"),
            warnings=state.get("warnings", []) + state.get("guardrail_reasons", []),
            metrics=state.get("metrics", {}),
        )
