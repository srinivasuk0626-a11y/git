from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from resolveai.domain.models import ServiceRequest
from resolveai.llm.rules import RuleBasedDecisionEngine
from resolveai.observability.audit import AuditLedger
from resolveai.retrieval.loader import load_identities, load_policies
from resolveai.retrieval.memory import InMemoryPolicyRetriever
from resolveai.tools.identity import IdentityService
from resolveai.tools.ticketing import TicketService
from resolveai.workflow.native import NativeResolutionWorkflow, WorkflowDependencies


async def main() -> None:
    cases = [json.loads(line) for line in Path("evals/cases.jsonl").read_text().splitlines() if line]
    with TemporaryDirectory() as directory:
        temp = Path(directory)
        tickets = TicketService(temp / "tickets.db")
        await tickets.initialize()
        workflow = NativeResolutionWorkflow(
            WorkflowDependencies(
                retriever=InMemoryPolicyRetriever(load_policies(Path("data"))),
                identity_service=IdentityService(load_identities(Path("data"))),
                ticket_service=tickets,
                decision_engine=RuleBasedDecisionEngine(),
                audit_ledger=AuditLedger(temp / "audit.jsonl"),
            )
        )
        passed = 0
        details = []
        for index, case in enumerate(cases):
            result = await workflow.start(f"eval-{index}", ServiceRequest.model_validate(case["request"]))
            checks = {
                "status": result.status.value == case["expected_status"],
                "approval": result.approval_required == case["approval_required"],
                "type": case["expected_type"] is None or (result.request_type and result.request_type.value == case["expected_type"]),
            }
            ok = all(checks.values())
            passed += int(ok)
            details.append({"id": case["id"], "passed": ok, "checks": checks, "result": result.model_dump(mode="json")})

    report = {"passed": passed, "total": len(cases), "accuracy": passed / len(cases), "details": details}
    Path("evals/report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "total", "accuracy")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
