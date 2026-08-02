from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from resolveai.domain.models import PolicyDocument, SearchHit
from resolveai.retrieval.base import PolicyRetriever


class ElasticsearchPolicyRetriever(PolicyRetriever):
    def __init__(
        self,
        *,
        url: str,
        index_name: str,
        api_key: str | None = None,
        semantic_enabled: bool = False,
    ) -> None:
        kwargs: dict[str, Any] = {"hosts": [url]}
        if api_key:
            kwargs["api_key"] = api_key
        self._client = AsyncElasticsearch(**kwargs)
        self._index_name = index_name
        self._semantic_enabled = semantic_enabled

    async def ensure_index(self) -> None:
        if await self._client.indices.exists(index=self._index_name):
            return
        properties: dict[str, Any] = {
            "policy_id": {"type": "keyword"},
            "policy_key": {"type": "keyword"},
            "title": {"type": "text"},
            "version": {"type": "integer"},
            "department": {"type": "keyword"},
            "status": {"type": "keyword"},
            "effective_from": {"type": "date"},
            "expires_at": {"type": "date"},
            "content": {"type": "text"},
            "rules": {"type": "flattened"},
            "source_uri": {"type": "keyword"},
            "updated_at": {"type": "date"},
            "suspicious": {"type": "boolean"},
        }
        if self._semantic_enabled:
            properties["semantic_content"] = {"type": "semantic_text"}
        await self._client.indices.create(
            index=self._index_name,
            mappings={"properties": properties},
        )

    async def index(self, documents: list[PolicyDocument]) -> int:
        await self.ensure_index()

        async def actions():
            for document in documents:
                source = document.model_dump(mode="json")
                if self._semantic_enabled:
                    source["semantic_content"] = f"{document.title}\n{document.content}"
                yield {
                    "_op_type": "index",
                    "_index": self._index_name,
                    "_id": document.policy_id,
                    "_source": source,
                }

        success, _ = await async_bulk(self._client, actions(), refresh="wait_for")
        return success

    async def search(self, query: str, *, department: str, top_k: int) -> list[SearchHit]:
        filters = [
            {"terms": {"department": [department, "global"]}},
            {"term": {"status": "active"}},
            {"term": {"suspicious": False}},
        ]
        if self._semantic_enabled:
            retriever: dict[str, Any] = {
                "rrf": {
                    "retrievers": [
                        {
                            "standard": {
                                "query": {
                                    "bool": {
                                        "must": [{"multi_match": {"query": query, "fields": ["title^3", "content"]}}],
                                        "filter": filters,
                                    }
                                }
                            }
                        },
                        {
                            "standard": {
                                "query": {
                                    "bool": {
                                        "must": [{"semantic": {"field": "semantic_content", "query": query}}],
                                        "filter": filters,
                                    }
                                }
                            }
                        },
                    ],
                    "rank_window_size": max(20, top_k * 4),
                    "rank_constant": 60,
                }
            }
            response = await self._client.search(
                index=self._index_name,
                retriever=retriever,
                size=top_k,
            )
        else:
            response = await self._client.search(
                index=self._index_name,
                query={
                    "bool": {
                        "must": [{"multi_match": {"query": query, "fields": ["title^3", "content"]}}],
                        "filter": filters,
                    }
                },
                size=top_k,
            )

        return [
            SearchHit(
                document=PolicyDocument.model_validate(hit["_source"]),
                score=float(hit.get("_score") or 0.0),
                matched_terms=[],
            )
            for hit in response["hits"]["hits"]
        ]

    async def close(self) -> None:
        await self._client.close()
