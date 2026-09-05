import os
import json
import pytest
import uuid
from unittest.mock import patch, MagicMock

from src.agents.tools import execute_search_with_retry, flaky_tool_attempts
from src.config.logger import LOG_FILE, log_agent_activity

def test_flaky_tool_retry():
    task_id = str(uuid.uuid4())
    flaky_tool_attempts[task_id] = 0
    query = "__FLAKY_TEST__"

    # Execution should fail on attempt 0, catch exception, retry, and succeed on attempt 1
    result = execute_search_with_retry(query, task_id=task_id, max_retries=2)
    assert "Search results retrieved on second attempt" in result

    # Check structured log file for failure and retry entries
    assert os.path.exists(LOG_FILE)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f.readlines() if line.strip()]

    task_logs = [l for l in lines if l.get("task_id") == task_id]
    assert len(task_logs) >= 2
    
    actions = [l.get("action_details") for l in task_logs]
    assert any("failed on initial attempt" in a for a in actions)
    assert any("Retrying tool execution" in a for a in actions)

def test_structured_json_logging_format():
    task_id = str(uuid.uuid4())
    log_agent_activity(task_id, "TestAgent", "Executing test action")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f.readlines() if line.strip()]
    
    matching_log = next((l for l in lines if l.get("task_id") == task_id), None)
    assert matching_log is not None
    assert "timestamp" in matching_log
    assert matching_log["agent_name"] == "TestAgent"
    assert matching_log["action_details"] == "Executing test action"
