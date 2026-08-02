from enum import StrEnum


class RequestType(StrEnum):
    ACCESS_REQUEST = "access_request"
    INCIDENT = "incident"
    DATA_QUESTION = "data_question"
    POLICY_QUESTION = "policy_question"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowStatus(StrEnum):
    RECEIVED = "received"
    BLOCKED = "blocked"
    PENDING_APPROVAL = "pending_approval"
    DENIED = "denied"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    FAILED = "failed"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
