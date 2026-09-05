import time
from src.config.logger import log_agent_activity

flaky_tool_attempts = {}

def simulated_search_tool(query: str, task_id: str = "unknown") -> str:
    """
    Simulated search tool.
    If query equals or contains '__FLAKY_TEST__', it raises an Exception on attempt 0
    and succeeds on subsequent attempts.
    """
    if "__FLAKY_TEST__" in query:
        attempts = flaky_tool_attempts.get(task_id, 0)
        if attempts == 0:
            flaky_tool_attempts[task_id] = 1
            log_agent_activity(
                task_id=task_id,
                agent_name="ResearchAgent",
                action_details="Tool execution failed on initial attempt for '__FLAKY_TEST__': Simulated transient network timeout."
            )
            raise Exception("Simulated transient network timeout.")
        else:
            log_agent_activity(
                task_id=task_id,
                agent_name="ResearchAgent",
                action_details="Retrying tool execution for '__FLAKY_TEST__' (attempt 2)"
            )
            return "Search results retrieved on second attempt: LangGraph supports stateful graphs and Human-in-the-loop, while CrewAI provides role-based agent collaboration."

    # Normal prompt / search query
    log_agent_activity(
        task_id=task_id,
        agent_name="ResearchAgent",
        action_details=f"Searching for information on query: {query}"
    )
    return (
        "LangGraph Key Features: Stateful graph-based orchestration, persistent checkpointers, "
        "first-class human-in-the-loop control flow, fine-grained cyclic agent workflows. "
        "CrewAI Key Features: Role-based AI agent team delegation, sequential and hierarchical task execution, "
        "autonomous tool usage, lightweight agent definitions."
    )

def execute_search_with_retry(query: str, task_id: str, max_retries: int = 2) -> str:
    """
    Executes simulated_search_tool with retry logic to ensure fault tolerance.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            result = simulated_search_tool(query, task_id=task_id)
            return result
        except Exception as e:
            last_exception = e
            # Small delay before retry
            time.sleep(0.1)
    
    raise last_exception
