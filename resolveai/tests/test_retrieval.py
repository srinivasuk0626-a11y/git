from pathlib import Path

import pytest

from resolveai.retrieval.loader import load_policies
from resolveai.retrieval.memory import InMemoryPolicyRetriever


@pytest.mark.asyncio
async def test_active_access_policy_ranks_above_archived_policy() -> None:
    retriever = InMemoryPolicyRetriever(load_policies(Path("data")))
    hits = await retriever.search(
        "production analytics access manager approval",
        department="analytics",
        top_k=5,
    )
    safe_ids = [hit.document.policy_id for hit in hits if not hit.document.suspicious]
    assert safe_ids[0] == "POL-ACCESS-004"
    assert "POL-MALICIOUS-001" not in safe_ids
