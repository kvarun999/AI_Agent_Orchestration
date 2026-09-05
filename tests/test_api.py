import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.main import app
from src.db.session import init_db

init_db()
client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("src.api.routes.run_agent_workflow.delay")
def test_create_task(mock_celery_delay):
    prompt_text = "Research the key features of LangGraph and CrewAI. Write a short comparison summary for a technical audience."
    response = client.post("/api/v1/tasks", json={"prompt": prompt_text})
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "PENDING"
    mock_celery_delay.assert_called_once()

    # Retrieve task via GET endpoint
    task_id = data["task_id"]
    get_res = client.get(f"/api/v1/tasks/{task_id}")
    assert get_res.status_code == 200
    task_data = get_res.json()
    assert task_data["id"] == task_id
    assert task_data["prompt"] == prompt_text
    assert task_data["status"] == "PENDING"
    assert "agent_logs" in task_data
    assert "created_at" in task_data
    assert "updated_at" in task_data

@patch("src.api.routes.resume_agent_workflow.delay")
@patch("src.api.routes.run_agent_workflow.delay")
def test_approve_task(mock_run_delay, mock_resume_delay):
    create_res = client.post("/api/v1/tasks", json={"prompt": "Test approval flow"})
    task_id = create_res.json()["task_id"]

    approve_res = client.post(
        f"/api/v1/tasks/{task_id}/approve",
        json={"approved": True, "feedback": "Looks good to proceed."}
    )
    assert approve_res.status_code == 200
    approve_data = approve_res.json()
    assert approve_data["task_id"] == task_id
    assert approve_data["status"] == "RESUMED"
    mock_resume_delay.assert_called_once()
