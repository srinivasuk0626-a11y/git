from fastapi.testclient import TestClient

from resolveai.api.main import app


def test_health_and_request_workflow() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        response = client.post(
            "/v1/requests",
            json={
                "requester_id": "usr-1001",
                "department": "analytics",
                "text": "Restore access to the production analytics workspace",
                "requested_resource": "prod-analytics",
                "business_justification": "Quarterly reconciliation",
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "pending_approval"
        approved = client.post(
            f"/v1/requests/{payload['thread_id']}/approval",
            json={
                "decision": "approve",
                "reviewer_id": "manager-2001",
                "comment": "Approved for 30 days",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "completed"
        assert approved.json()["ticket"]["ticket_id"].startswith("INC-")
