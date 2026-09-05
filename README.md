# Asynchronous Multi-Agent System with LangGraph, Celery, Redis, PostgreSQL & FastAPI

A production-grade, containerized multi-agent orchestration ecosystem built with **LangGraph**, **FastAPI**, **Celery**, **Redis**, and **PostgreSQL**.

The architecture enables autonomous, specialized AI agents to collaborate on multi-step workflows while supporting **Human-in-the-Loop (HITL)** approvals, **real-time WebSocket streaming**, **ephemeral Redis scratchpad memory**, **PostgreSQL state persistence**, **fault-tolerant tool retries**, and **structured JSON log tracing**.

---

## System Architecture

```
                                  +----------------------+
                                  |   Client / Frontend  |
                                  +----------+-----------+
                                             |
                   HTTP POST /tasks          |  WebSocket /ws/tasks/{id}
                   HTTP POST /approve        v
                                  +----------------------+
                                  |    FastAPI Server    |
                                  +---+--------------+---+
                                      |              ^
                       Enqueue Task   |              | Subscribe (Redis PubSub)
                       (Celery Delay) v              |
                                  +------------------+---+
                                  |   Redis Broker /     |
                                  |   PubSub / Scratch   |
                                  +---+------------------+
                                      |
                       Consume Task   v
                                  +----------------------+
                                  |    Celery Worker     |
                                  | (LangGraph Workflow) |
                                  +---+--------------+---+
                                      |              |
                     Read/Write State |              | Persist Task & Agent Logs
                                      v              v
                                  +-------+      +-------+
                                  | Redis |      | Postgres|
                                  +-------+      +-------+
```

---

## Features & Highlights

1. **Containerized Multi-Service Orchestration**: Fully configured with Docker Compose, featuring health checks for `db` (PostgreSQL), `redis`, `api` (FastAPI), and `worker` (Celery).
2. **LangGraph State Machine Orchestration**: Multi-phase workflow comprising a `ResearchAgent`, an intermediate `WritingAgent` draft phase, a `Human-in-the-Loop` decision gate, and a final `WritingAgent` completion phase.
3. **Redis Shared Scratchpad**: Decouples heavy intermediate research data from PostgreSQL by storing transient artifacts under key `task:<task_id>:workspace`.
4. **PostgreSQL Persistent Audit Trail**: Tracks task lifecycle states (`PENDING`, `RUNNING`, `AWAITING_APPROVAL`, `RESUMED`, `COMPLETED`, `FAILED`) and maintains structured agent execution logs in `agent_logs` (JSONB).
5. **Real-time WebSocket Streaming**: Streams live status transitions to connected clients at `/ws/tasks/{task_id}` using Redis Pub/Sub (`task_updates:<task_id>`).
6. **Fault Tolerance & Automated Retries**: Implements automatic retry handling for flaky tool execution (e.g. `__FLAKY_TEST__`), writing error trace logs and retry attempts to `logs/agent_activity.log`.
7. **Structured Machine-Readable Logging**: Records all agent activities in structured JSON format at `logs/agent_activity.log` with required fields (`timestamp`, `task_id`, `agent_name`, `action_details`).

---

## Directory Structure

```
.
├── docker-compose.yml       # Service orchestration (API, Worker, DB, Redis)
├── Dockerfile               # Blueprint for Python container services
├── .env.example             # Environment configuration template
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
├── logs/                    # Directory for structured agent logs
│   └── agent_activity.log
├── src/
│   ├── main.py              # FastAPI entrypoint & application initialization
│   ├── api/                 # REST endpoints & WebSocket routing
│   ├── worker/              # Celery application & task definitions
│   ├── agents/              # LangGraph workflow, nodes, & tool retry logic
│   ├── db/                  # PostgreSQL SQLAlchemy models & session helpers
│   └── config/              # Environment configuration & structured logger
└── tests/                   # Automated pytest suite
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) installed on Linux/macOS/Windows.

### Quickstart with Docker Compose

1. **Clone the repository** and navigate to the project directory:
   ```bash
   git clone <repository_url>
   cd AI_agent_orchestration
   ```

2. **Set up Environment Variables**:
   ```bash
   cp .env.example .env
   ```

3. **Build and start all services**:
   ```bash
   docker-compose up --build
   ```

4. **Verify container health**:
   All 4 services (`db`, `redis`, `api`, `worker`) will initialize and report healthy status within 1–2 minutes.

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | Application healthcheck (returns `{"status": "ok"}`) |
| **POST** | `/api/v1/tasks` | Queues a new multi-agent research workflow |
| **GET** | `/api/v1/tasks/{task_id}` | Retrieves status, result, and `agent_logs` for a task |
| **POST** | `/api/v1/tasks/{task_id}/approve` | Submits human approval to resume a paused task |
| **WS** | `/ws/tasks/{task_id}` | WebSocket stream for real-time task status updates |

---

## End-to-End Walkthrough Example

### 1. Initiate a Task
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Research the key features of LangGraph and CrewAI. Write a short comparison summary for a technical audience."}'
```
**Response (202 Accepted)**:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "PENDING"
}
```

### 2. Connect WebSocket to Stream Updates
Connect to `ws://localhost:8000/ws/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ab` using `wscat` or a WebSocket client:
```bash
wscat -c ws://localhost:8000/ws/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ab
```
**Stream Output**:
```json
{"task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab", "status": "RUNNING"}
{"task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab", "status": "AWAITING_APPROVAL"}
```

### 3. Check Task Details
```bash
curl http://localhost:8000/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ab
```

### 4. Provide Human Approval
```bash
curl -X POST http://localhost:8000/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ab/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": "Approved for publication."}'
```
**Response (200 OK)**:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "RESUMED"
}
```

### 5. Final Retrieval
Poll `GET /api/v1/tasks/{task_id}` until `"status": "COMPLETED"`. The `"result"` field will contain the synthesized comparison summary and `"agent_logs"` will record the step audit trail.

---

## Testing Fault Tolerance

To test the simulated flaky tool retry logic, initiate a task with `__FLAKY_TEST__` in the prompt:
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "__FLAKY_TEST__ Research LangGraph features"}'
```
Inspect `logs/agent_activity.log`:
```json
{"timestamp": "2026-09-05T12:00:00.000Z", "task_id": "...", "agent_name": "ResearchAgent", "action_details": "Tool execution failed on initial attempt for '__FLAKY_TEST__': Simulated transient network timeout."}
{"timestamp": "2026-09-05T12:00:00.100Z", "task_id": "...", "agent_name": "ResearchAgent", "action_details": "Retrying tool execution for '__FLAKY_TEST__' (attempt 2)"}
```

---

## Running Automated Tests

Run the test suite inside the container or local Python environment:
```bash
pytest tests/
```
