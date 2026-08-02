from __future__ import annotations

from resolveai.domain.enums import RequestType, RiskLevel
from resolveai.domain.models import ActionPlan, IdentityRecord, PolicyDocument, ServiceRequest
from resolveai.llm.base import DecisionEngine


class RuleBasedDecisionEngine(DecisionEngine):
    ACCESS_TERMS = {"access", "permission", "role", "entitlement", "restore", "grant"}
    INCIDENT_TERMS = {"failed", "failure", "outage", "broken", "incident", "error", "down"}
    POLICY_TERMS = {"policy", "allowed", "requirement", "approval", "compliance"}
    DATA_TERMS = {"data", "table", "dataset", "report", "metric", "dashboard"}

    async def classify(self, request: ServiceRequest) -> RequestType:
        terms = set(request.text.lower().replace("/", " ").split())
        if terms & self.ACCESS_TERMS:
            return RequestType.ACCESS_REQUEST
        if terms & self.INCIDENT_TERMS:
            return RequestType.INCIDENT
        if terms & self.POLICY_TERMS:
            return RequestType.POLICY_QUESTION
        if terms & self.DATA_TERMS:
            return RequestType.DATA_QUESTION
        return RequestType.UNKNOWN

    async def propose_plan(
        self,
        *,
        request: ServiceRequest,
        request_type: RequestType,
        identity: IdentityRecord | None,
        policies: list[PolicyDocument],
        warnings: list[str],
    ) -> ActionPlan:
        active = [policy for policy in policies if policy.is_active() and not policy.suspicious]
        evidence = [policy.policy_id for policy in active]
        unresolved: list[str] = []
        reasons: list[str] = []

        if identity is None:
            unresolved.append("Requester identity could not be verified")
        if not active:
            unresolved.append("No current policy evidence was found")
        if request_type == RequestType.ACCESS_REQUEST and not request.business_justification:
            unresolved.append("Business justification is required")

        if "policy_conflict" in warnings:
            reasons.append("Conflicting active policy rules require analyst review")
        if "suspicious_policy_quarantined" in warnings:
            reasons.append("A suspicious retrieved document was excluded")

        if request_type == RequestType.ACCESS_REQUEST:
            action = "restore_access" if "restore" in request.text.lower() else "grant_access"
            requires_approval = True
            risk = RiskLevel.HIGH
            tool_name = "create_service_ticket"
        elif request_type == RequestType.INCIDENT:
            action = "create_incident"
            requires_approval = False
            risk = RiskLevel.MEDIUM
            tool_name = "create_service_ticket"
        elif request_type in {RequestType.POLICY_QUESTION, RequestType.DATA_QUESTION}:
            action = "answer_with_policy_evidence"
            requires_approval = False
            risk = RiskLevel.LOW
            tool_name = None
        else:
            action = "route_to_service_desk"
            requires_approval = False
            risk = RiskLevel.MEDIUM
            tool_name = "create_service_ticket"

        if unresolved or "policy_conflict" in warnings:
            action = "escalate_for_manual_review"
            requires_approval = False
            risk = RiskLevel.HIGH
            tool_name = "create_service_ticket"

        summary = f"{request_type.value.replace('_', ' ').title()} for {request.requested_resource or 'unspecified resource'}"
        return ActionPlan(
            request_type=request_type,
            summary=summary,
            evidence_policy_ids=evidence,
            proposed_action=action,
            tool_name=tool_name,
            tool_arguments={
                "category": request_type.value,
                "summary": summary,
                "requested_resource": request.requested_resource,
            },
            requires_approval=requires_approval,
            risk_level=risk,
            reasons=reasons,
            unresolved_questions=unresolved,
        )
