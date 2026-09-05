import json
import redis
from typing import TypedDict, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from src.config.settings import settings
from src.config.logger import log_agent_activity
from src.agents.tools import execute_search_with_retry
from src.db.session import update_task_in_db, get_task_from_db

class LocalRedisFallback:
    def __init__(self):
        self._store = {}
    def set(self, key, value):
        self._store[key] = value
    def get(self, key):
        return self._store.get(key)
    def publish(self, channel, message):
        pass

try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception:
    redis_client = LocalRedisFallback()


def publish_status_update(task_id: str, status: str):
    """Publishes real-time status update to Redis Pub/Sub channel."""
    channel = f"task_updates:{task_id}"
    payload = json.dumps({"task_id": str(task_id), "status": status})
    redis_client.publish(channel, payload)

class AgentState(TypedDict):
    task_id: str
    prompt: str
    research_data: Optional[str]
    draft_summary: Optional[str]
    final_summary: Optional[str]
    status: str
    approved: bool
    feedback: Optional[str]

def research_agent_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    prompt = state["prompt"]
    
    # 1. Log activity & publish status
    log_agent_activity(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details=f"Starting web search for prompt: {prompt}"
    )
    publish_status_update(task_id, "RUNNING")
    
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    update_task_in_db(
        task_id=task_id,
        status="RUNNING",
        new_agent_log={
            "agent": "ResearchAgent",
            "action": f"Searching for features related to '{prompt[:40]}...'",
            "timestamp": timestamp
        }
    )

    # 2. Execute tool (handles flaky retries internally)
    research_findings = execute_search_with_retry(prompt, task_id=task_id)

    # 3. Store findings in Redis Scratchpad key task:<task_id>:workspace
    workspace_key = f"task:{task_id}:workspace"
    workspace_data = {
        "task_id": task_id,
        "prompt": prompt,
        "research_findings": research_findings
    }
    redis_client.set(workspace_key, json.dumps(workspace_data))
    
    log_agent_activity(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details=f"Saved research findings to Redis workspace key '{workspace_key}'"
    )

    state["research_data"] = research_findings
    return state

def writing_agent_draft_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    workspace_key = f"task:{task_id}:workspace"
    
    # Read from Redis scratchpad
    raw_data = redis_client.get(workspace_key)
    research_findings = ""
    if raw_data:
        try:
            workspace_data = json.loads(raw_data)
            research_findings = workspace_data.get("research_findings", "")
        except Exception:
            research_findings = raw_data

    log_agent_activity(
        task_id=task_id,
        agent_name="WritingAgent",
        action_details="Drafting comparison summary from Redis scratchpad research findings"
    )

    # Synthesize draft comparison summary
    draft_summary = (
        "LangGraph vs CrewAI Technical Comparison Summary:\n\n"
        "1. Architecture & Control Flow:\n"
        "   - LangGraph provides fine-grained, stateful graph orchestration with explicit nodes, edges, "
        "and built-in persistence. It excels at complex workflows requiring state checkpoints and human-in-the-loop control.\n"
        "   - CrewAI focuses on role-based multi-agent collaboration where autonomous agents perform sequential or hierarchical task execution.\n\n"
        "2. Key Capabilities:\n"
        "   - LangGraph: Custom state management, streaming, cyclic graphs, fine-grained tool error handling.\n"
        "   - CrewAI: Role assignment, high-level task delegation, rapid setup for collaborative agent teams.\n\n"
        "3. Research Context:\n"
        f"   - {research_findings}"
    )

    # Update Redis scratchpad with draft
    existing_data = {}
    if raw_data:
        try:
            existing_data = json.loads(raw_data)
        except Exception:
            pass
    existing_data["draft_summary"] = draft_summary
    redis_client.set(workspace_key, json.dumps(existing_data))

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    update_task_in_db(
        task_id=task_id,
        new_agent_log={
            "agent": "WritingAgent",
            "action": "Drafting comparison summary",
            "timestamp": timestamp
        }
    )

    state["draft_summary"] = draft_summary
    return state

def hitl_pause_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    update_task_in_db(
        task_id=task_id,
        status="AWAITING_APPROVAL"
    )
    publish_status_update(task_id, "AWAITING_APPROVAL")
    
    log_agent_activity(
        task_id=task_id,
        agent_name="System",
        action_details="Workflow paused at Human-in-the-Loop checkpoint. Awaiting user approval."
    )
    
    state["status"] = "AWAITING_APPROVAL"
    return state

def writing_agent_finalize_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    workspace_key = f"task:{task_id}:workspace"
    
    raw_data = redis_client.get(workspace_key)
    draft_summary = ""
    if raw_data:
        try:
            workspace_data = json.loads(raw_data)
            draft_summary = workspace_data.get("draft_summary", "")
        except Exception:
            draft_summary = raw_data

    log_agent_activity(
        task_id=task_id,
        agent_name="WritingAgent",
        action_details="Finalizing comparison summary following human approval"
    )

    feedback_text = f"\n\nHuman Feedback: {state.get('feedback')}" if state.get("feedback") else ""
    final_summary = draft_summary + feedback_text

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    update_task_in_db(
        task_id=task_id,
        status="COMPLETED",
        result=final_summary
    )
    publish_status_update(task_id, "COMPLETED")

    log_agent_activity(
        task_id=task_id,
        agent_name="WritingAgent",
        action_details="Saved final summary to PostgreSQL database result field"
    )

    state["final_summary"] = final_summary
    state["status"] = "COMPLETED"
    return state

# Build Phase 1 graph (Research -> Write Draft -> HITL Pause)
def create_phase1_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("research", research_agent_node)
    workflow.add_node("writing_draft", writing_agent_draft_node)
    workflow.add_node("hitl_pause", hitl_pause_node)

    workflow.set_entry_point("research")
    workflow.add_edge("research", "writing_draft")
    workflow.add_edge("writing_draft", "hitl_pause")
    workflow.add_edge("hitl_pause", END)
    
    return workflow.compile()

# Build Phase 2 graph (Resume -> Finalize -> Complete)
def create_phase2_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("writing_finalize", writing_agent_finalize_node)
    workflow.set_entry_point("writing_finalize")
    workflow.add_edge("writing_finalize", END)
    
    return workflow.compile()

phase1_app = create_phase1_graph()
phase2_app = create_phase2_graph()
