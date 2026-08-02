from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from resolveai.api.dependencies import ApplicationContainer, build_container
from resolveai.api.schemas import ApprovalBody, CreateRequestBody
from resolveai.config import get_settings
from resolveai.domain.models import WorkflowResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await build_container(get_settings())
    app.state.container = container
    yield
    await container.close()


app = FastAPI(
    title="ResolveAI",
    version="0.1.0",
    description="Secure, policy-grounded enterprise service resolution agent",
    lifespan=lifespan,
)


def container_from(request: Request) -> ApplicationContainer:
    return request.app.state.container


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    container = container_from(request)
    return {"status": "ok", "environment": container.settings.app_env}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/requests", response_model=WorkflowResult, status_code=status.HTTP_202_ACCEPTED)
async def create_request(body: CreateRequestBody, request: Request) -> WorkflowResult:
    container = container_from(request)
    if len(body.text) > container.settings.max_request_chars:
        raise HTTPException(status_code=413, detail="Request text exceeds configured limit")
    thread_id = str(uuid4())
    return await container.workflow.start(thread_id, body)


@app.post("/v1/requests/{thread_id}/approval", response_model=WorkflowResult)
async def approve_request(
    thread_id: str,
    body: ApprovalBody,
    request: Request,
) -> WorkflowResult:
    try:
        return await container_from(request).workflow.approve(
            thread_id,
            decision=body.decision,
            reviewer_id=body.reviewer_id,
            comment=body.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/requests/{thread_id}", response_model=WorkflowResult)
async def get_request(thread_id: str, request: Request) -> WorkflowResult:
    try:
        return await container_from(request).workflow.get(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
