from __future__ import annotations

from dataclasses import dataclass

from resolveai.config import Settings
from resolveai.llm.base import DecisionEngine
from resolveai.llm.openai_compatible import OpenAICompatibleDecisionEngine
from resolveai.llm.rules import RuleBasedDecisionEngine
from resolveai.observability.audit import AuditLedger
from resolveai.retrieval.base import PolicyRetriever
from resolveai.retrieval.loader import load_identities, load_policies
from resolveai.retrieval.memory import InMemoryPolicyRetriever
from resolveai.tools.identity import IdentityService
from resolveai.tools.ticketing import TicketService
from resolveai.workflow.native import NativeResolutionWorkflow, WorkflowDependencies


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    retriever: PolicyRetriever
    decision_engine: DecisionEngine
    workflow: NativeResolutionWorkflow

    async def close(self) -> None:
        await self.retriever.close()
        await self.decision_engine.close()


async def build_container(settings: Settings) -> ApplicationContainer:
    policies = load_policies(settings.data_dir)
    identities = load_identities(settings.data_dir)

    if settings.retrieval_backend == "elasticsearch":
        from resolveai.retrieval.elastic import ElasticsearchPolicyRetriever

        retriever: PolicyRetriever = ElasticsearchPolicyRetriever(
            url=settings.elasticsearch_url,
            index_name=settings.elasticsearch_index,
            api_key=settings.elasticsearch_api_key,
            semantic_enabled=settings.elastic_semantic_enabled,
        )
        await retriever.index(policies)
    else:
        retriever = InMemoryPolicyRetriever(policies)

    if settings.decision_engine == "openai_compatible":
        if not settings.openai_compatible_model:
            raise ValueError("OPENAI_COMPATIBLE_MODEL is required when DECISION_ENGINE=openai_compatible")
        decision_engine: DecisionEngine = OpenAICompatibleDecisionEngine(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    else:
        decision_engine = RuleBasedDecisionEngine()

    ticket_service = TicketService(settings.ticket_db_path)
    await ticket_service.initialize()
    workflow = NativeResolutionWorkflow(
        WorkflowDependencies(
            retriever=retriever,
            identity_service=IdentityService(identities),
            ticket_service=ticket_service,
            decision_engine=decision_engine,
            audit_ledger=AuditLedger(settings.audit_log_path),
            policy_top_k=settings.policy_top_k,
        )
    )
    return ApplicationContainer(
        settings=settings,
        retriever=retriever,
        decision_engine=decision_engine,
        workflow=workflow,
    )
