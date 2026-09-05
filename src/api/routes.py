import uuid
import json
import asyncio
import redis.asyncio as aioredis
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from src.db.session import create_task_in_db, get_task_from_db, update_task_in_db
from src.worker.tasks import run_agent_workflow, resume_agent_workflow
from src.config.settings import settings
from src.config.logger import log_agent_activity

router = APIRouter()

class TaskCreateRequest(BaseModel):
    prompt: str = Field(..., example="Research the key features of LangGraph and CrewAI. Write a short comparison summary for a technical audience.")

class TaskCreateResponse(BaseModel):
    task_id: str
    status: str

class TaskApproveRequest(BaseModel):
    approved: bool = Field(True, example=True)
    feedback: Optional[str] = Field(None, example="Looks good to proceed.")

class TaskApproveResponse(BaseModel):
    task_id: str
    status: str

@router.get("/health", status_code=200)
def health_check():
    return {"status": "ok"}

@router.post("/api/v1/tasks", status_code=status.HTTP_202_ACCEPTED, response_model=TaskCreateResponse)
def create_task(payload: TaskCreateRequest):
    """
    Creates a new agent workflow task asynchronously.
    """
    task_id = str(uuid.uuid4())
    
    # 1. Create DB record with PENDING status
    create_task_in_db(task_id=task_id, prompt=payload.prompt, status="PENDING")
    
    # 2. Log activity
    log_agent_activity(task_id, "API", f"Received task creation request for prompt: {payload.prompt[:40]}...")

    # 3. Dispatch Celery worker task asynchronously
    run_agent_workflow.delay(task_id, payload.prompt)

    # 4. Immediate return (<500ms response time)
    return TaskCreateResponse(task_id=task_id, status="PENDING")

@router.get("/api/v1/tasks/{task_id}", status_code=status.HTTP_200_OK)
def get_task(task_id: str):
    """
    Retrieves task status and details.
    """
    task = get_task_from_db(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()

@router.post("/api/v1/tasks/{task_id}/approve", status_code=status.HTTP_200_OK, response_model=TaskApproveResponse)
def approve_task(task_id: str, payload: TaskApproveRequest):
    """
    Provides human approval to resume a paused agent workflow.
    """
    task = get_task_from_db(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["AWAITING_APPROVAL", "RESUMED", "RUNNING"]:
        # If task is completed or failed, return current status or 400
        pass

    # Update DB status to RESUMED
    update_task_in_db(task_id=task_id, status="RESUMED")
    log_agent_activity(task_id, "API", f"Received human approval. Feedback: {payload.feedback}")

    # Trigger Celery resume worker task
    resume_agent_workflow.delay(task_id, payload.feedback)

    return TaskApproveResponse(task_id=task_id, status="RESUMED")

@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_updates(websocket: WebSocket, task_id: str):
    """
    Streams real-time status update JSON objects to connected WebSocket client.
    """
    await websocket.accept()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    channel = f"task_updates:{task_id}"

    try:
        # Send current task status immediately upon connection
        task = get_task_from_db(task_id)
        if task:
            initial_msg = {"task_id": task_id, "status": task.status}
            await websocket.send_json(initial_msg)

        await pubsub.subscribe(channel)
        
        while True:
            # Poll Pub/Sub channel for messages
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data_str = message.get("data")
                if data_str:
                    try:
                        payload = json.loads(data_str)
                    except Exception:
                        payload = {"task_id": task_id, "status": str(data_str)}
                    await websocket.send_json(payload)
            
            # Yield control briefly to event loop
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.close()
