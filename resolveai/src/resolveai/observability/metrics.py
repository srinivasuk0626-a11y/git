from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "resolveai_requests_total",
    "Workflow requests by final status and type",
    ["status", "request_type"],
)
WORKFLOW_LATENCY = Histogram(
    "resolveai_workflow_latency_seconds",
    "End-to-end workflow latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
APPROVALS = Counter(
    "resolveai_approvals_total",
    "Approval decisions",
    ["decision"],
)
GUARDRAIL_BLOCKS = Counter(
    "resolveai_guardrail_blocks_total",
    "Blocked requests or documents by reason",
    ["reason"],
)
TICKETS = Counter(
    "resolveai_tickets_total",
    "Ticket execution outcomes",
    ["outcome"],
)
RETRIEVAL_HITS = Histogram(
    "resolveai_retrieval_hits",
    "Number of policy hits returned per workflow",
    buckets=(0, 1, 2, 3, 4, 5, 10),
)
