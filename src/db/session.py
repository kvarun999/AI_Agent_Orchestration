from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings
from src.db.models import Base, TaskModel
import uuid
from datetime import datetime, timezone
import json

db_url = settings.DATABASE_URL
try:
    engine = create_engine(db_url, pool_pre_ping=True)
    # Test connection creation
    with engine.connect() as conn:
        pass
except Exception:
    # Fallback to SQLite in-memory for local testing outside Docker if Postgres is unavailable
    db_url = "sqlite:///:memory:"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes database tables on startup."""
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_task_in_db(task_id: str, prompt: str, status: str = "PENDING") -> TaskModel:
    db = SessionLocal()
    try:
        task = TaskModel(
            id=uuid.UUID(str(task_id)),
            prompt=prompt,
            status=status,
            agent_logs=[]
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()

def get_task_from_db(task_id: str) -> TaskModel | None:
    db = SessionLocal()
    try:
        return db.query(TaskModel).filter(TaskModel.id == uuid.UUID(str(task_id))).first()
    finally:
        db.close()

def update_task_in_db(
    task_id: str,
    status: str | None = None,
    result: str | None = None,
    new_agent_log: dict | None = None
) -> TaskModel | None:
    db = SessionLocal()
    try:
        task = db.query(TaskModel).filter(TaskModel.id == uuid.UUID(str(task_id))).first()
        if not task:
            return None
        
        if status is not None:
            task.status = status
        if result is not None:
            task.result = result
        if new_agent_log is not None:
            logs = list(task.agent_logs or [])
            logs.append(new_agent_log)
            task.agent_logs = logs
        
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()
