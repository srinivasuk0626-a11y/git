from __future__ import annotations

import math
import re
from collections import Counter

from resolveai.domain.models import PolicyDocument, SearchHit
from resolveai.retrieval.base import PolicyRetriever
from resolveai.security.guardrails import inspect_untrusted_text

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]+")


def tokenize(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


class InMemoryPolicyRetriever(PolicyRetriever):
    def __init__(self, documents: list[PolicyDocument] | None = None) -> None:
        self._documents = documents or []

    async def index(self, documents: list[PolicyDocument]) -> int:
        by_id = {document.policy_id: document for document in self._documents}
        by_id.update({document.policy_id: document for document in documents})
        self._documents = list(by_id.values())
        return len(documents)

    async def search(self, query: str, *, department: str, top_k: int) -> list[SearchHit]:
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []

        candidates = [
            document
            for document in self._documents
            if document.department in {department, "global"}
        ]
        document_frequency: Counter[str] = Counter()
        document_terms: dict[str, Counter[str]] = {}
        for document in candidates:
            terms = Counter(tokenize(f"{document.title} {document.content}"))
            document_terms[document.policy_id] = terms
            document_frequency.update(terms.keys())

        hits: list[SearchHit] = []
        total = max(len(candidates), 1)
        for document in candidates:
            guardrail = inspect_untrusted_text(document.content, block_on_injection=False)
            if guardrail.reasons:
                document = document.model_copy(update={"suspicious": True})

            terms = document_terms[document.policy_id]
            matched: list[str] = []
            score = 0.0
            title_terms = set(tokenize(document.title))
            for term, query_frequency in query_terms.items():
                term_frequency = terms.get(term, 0)
                if not term_frequency:
                    continue
                matched.append(term)
                inverse_frequency = math.log((total + 1) / (document_frequency[term] + 0.5)) + 1
                title_boost = 1.75 if term in title_terms else 1.0
                score += query_frequency * math.log1p(term_frequency) * inverse_frequency * title_boost

            if document.is_active():
                score *= 1.15
            if document.suspicious:
                score *= 0.05
            if score > 0:
                hits.append(SearchHit(document=document, score=round(score, 6), matched_terms=matched))

        hits.sort(key=lambda hit: (hit.score, hit.document.version), reverse=True)
        return hits[:top_k]
