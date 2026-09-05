import logging
from src.worker.celery_app import celery_app
from src.agents.workflow import phase1_app, phase2_app
from src.db.session import update_task_in_db, init_db
from src.config.logger import log_agent_activity

# Ensure DB tables exist in worker process
init_db()

logger = logging.getLogger(__name__)

@celery_app.task(name="src.worker.tasks.run_agent_workflow")
def run_agent_workflow(task_id: str, prompt: str):
    """
    Celery task to execute Phase 1 of the multi-agent workflow (Research & Draft summary).
    """
    try:
        initial_state = {
            "task_id": task_id,
            "prompt": prompt,
            "research_data": None,
            "draft_summary": None,
            "final_summary": None,
            "status": "PENDING",
            "approved": False,
            "feedback": None
        }
        phase1_app.invoke(initial_state)
        return {"task_id": task_id, "status": "AWAITING_APPROVAL"}
    except Exception as exc:
        logger.error(f"Error executing agent workflow for task {task_id}: {exc}", exc_info=True)
        update_task_in_db(task_id, status="FAILED", result=str(exc))
        log_agent_activity(task_id, "System", f"Task workflow failed with error: {exc}")
        raise exc

@celery_app.task(name="src.worker.tasks.resume_agent_workflow")
def resume_agent_workflow(task_id: str, feedback: str = None):
    """
    Celery task to execute Phase 2 of the multi-agent workflow after human approval.
    """
    try:
        state = {
            "task_id": task_id,
            "prompt": "",
            "research_data": None,
            "draft_summary": None,
            "final_summary": None,
            "status": "RESUMED",
            "approved": True,
            "feedback": feedback
        }
        phase2_app.invoke(state)
        return {"task_id": task_id, "status": "COMPLETED"}
    except Exception as exc:
        logger.error(f"Error resuming agent workflow for task {task_id}: {exc}", exc_info=True)
        update_task_in_db(task_id, status="FAILED", result=str(exc))
        log_agent_activity(task_id, "System", f"Task workflow resume failed with error: {exc}")
        raise exc
