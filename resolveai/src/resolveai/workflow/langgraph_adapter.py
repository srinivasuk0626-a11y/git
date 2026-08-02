from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from resolveai.workflow.state import ResolutionState


class LangGraphApprovalAdapter:
    """Minimal LangGraph pattern for durable human approval.

    The production API uses the framework-independent workflow so its domain logic remains
    directly testable. This adapter demonstrates how the same approval boundary can be
    moved to LangGraph persistence without coupling business rules to graph primitives.
    """

    def __init__(self) -> None:
        builder = StateGraph(ResolutionState)
        builder.add_node("approval", self._approval_node)
        builder.add_node("complete", self._complete_node)
        builder.add_edge(START, "approval")
        builder.add_edge("approval", "complete")
        builder.add_edge("complete", END)
        self.graph = builder.compile(checkpointer=InMemorySaver())

    @staticmethod
    def _approval_node(state: ResolutionState) -> dict[str, Any]:
        decision = interrupt(
            {
                "type": "human_approval",
                "thread_id": state["thread_id"],
                "plan": state.get("plan", {}),
                "allowed_decisions": ["approve", "deny"],
            }
        )
        return {"approval": decision}

    @staticmethod
    def _complete_node(state: ResolutionState) -> dict[str, Any]:
        approval = state.get("approval") or {}
        return {
            "status": "completed" if approval.get("decision") == "approve" else "denied",
            "message": "LangGraph approval boundary completed.",
        }

    async def begin(self, state: ResolutionState) -> dict[str, Any]:
        config = {"configurable": {"thread_id": state["thread_id"]}}
        return await self.graph.ainvoke(state, config)

    async def resume(self, thread_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        return await self.graph.ainvoke(Command(resume=decision), config)
