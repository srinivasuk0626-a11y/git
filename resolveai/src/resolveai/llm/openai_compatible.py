from __future__ import annotations

import json
from typing import Any

import httpx

from resolveai.domain.enums import RequestType
from resolveai.domain.models import ActionPlan, IdentityRecord, PolicyDocument, ServiceRequest
from resolveai.llm.base import DecisionEngine


class OpenAICompatibleDecisionEngine(DecisionEngine):
    """Optional structured-output adapter for an OpenAI-compatible chat endpoint.

    Tool execution remains outside this class. Returned values are validated by Pydantic
    and then re-checked by workflow policy and authorization controls.
    """

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        self._model = model

    async def _json_completion(self, system: str, user: str) -> dict[str, Any]:
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    async def classify(self, request: ServiceRequest) -> RequestType:
        payload = await self._json_completion(
            "Classify enterprise service requests. Return only JSON with request_type.",
            json.dumps(
                {
                    "allowed": [item.value for item in RequestType],
                    "request": request.model_dump(mode="json"),
                }
            ),
        )
        return RequestType(payload["request_type"])

    async def propose_plan(
        self,
        *,
        request: ServiceRequest,
        request_type: RequestType,
        identity: IdentityRecord | None,
        policies: list[PolicyDocument],
        warnings: list[str],
    ) -> ActionPlan:
        payload = await self._json_completion(
            "Propose a conservative enterprise service plan. Never invent policy evidence. "
            "State-changing access actions must require approval. Return only JSON matching the supplied schema.",
            json.dumps(
                {
                    "request": request.model_dump(mode="json"),
                    "request_type": request_type.value,
                    "identity": identity.model_dump(mode="json") if identity else None,
                    "policies": [policy.model_dump(mode="json") for policy in policies],
                    "warnings": warnings,
                    "schema": ActionPlan.model_json_schema(),
                },
                default=str,
            ),
        )
        return ActionPlan.model_validate(payload)

    async def close(self) -> None:
        await self._client.aclose()
