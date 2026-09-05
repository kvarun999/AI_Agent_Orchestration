import os
import json
import logging
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOG_DIR, "agent_activity.log")

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("agent_activity")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if imported multiple times
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    # Use simple Formatter as we write raw JSON in log_agent_activity
    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def log_agent_activity(task_id: str, agent_name: str, action_details: str):
    """
    Logs agent activity in structured JSON format to logs/agent_activity.log.
    Required keys: timestamp, task_id, agent_name, action_details
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_entry = {
        "timestamp": timestamp,
        "task_id": str(task_id),
        "agent_name": agent_name,
        "action_details": action_details
    }
    json_line = json.dumps(log_entry)
    logger.info(json_line)
    # Ensure immediate flush to file
    for handler in logger.handlers:
        handler.flush()
