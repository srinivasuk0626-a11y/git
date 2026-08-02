import asyncio
from tempfile import TemporaryDirectory
from pathlib import Path

from resolveai.domain.enums import ApprovalDecision
from resolveai.domain.models import ServiceRequest
from resolveai.llm.rules import RuleBasedDecisionEngine
from resolveai.observability.audit import AuditLedger
from resolveai.retrieval.loader import load_identities, load_policies
from resolveai.retrieval.memory import InMemoryPolicyRetriever
from resolveai.tools.identity import IdentityService
from resolveai.tools.ticketing import TicketService
from resolveai.workflow.native import NativeResolutionWorkflow, WorkflowDependencies


async def main() -> None:
    data_dir = Path("data")
    with TemporaryDirectory() as directory:
        path = Path(directory)
        tickets = TicketService(path / "tickets.db")
        await tickets.initialize()
        workflow = NativeResolutionWorkflow(
            WorkflowDependencies(
                retriever=InMemoryPolicyRetriever(load_policies(data_dir)),
                identity_service=IdentityService(load_identities(data_dir)),
                ticket_service=tickets,
                decision_engine=RuleBasedDecisionEngine(),
                audit_ledger=AuditLedger(path / "audit.jsonl"),
            )
        )
        request = ServiceRequest(
            requester_id="usr-1001",
            department="analytics",
            text="Restore my access to the production analytics workspace.",
            requested_resource="prod-analytics",
            business_justification="Quarterly revenue reconciliation",
        )
        pending = await workflow.start("demo-thread", request)
        print(pending.model_dump_json(indent=2))
        completed = await workflow.approve(
            "demo-thread",
            decision=ApprovalDecision.APPROVE,
            reviewer_id="manager-2001",
            comment="Approved for 30 days",
        )
        print(completed.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
