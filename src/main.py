from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.db.session import init_db
from src.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas on startup
    init_db()
    yield

app = FastAPI(
    title="Asynchronous Multi-Agent Orchestrator",
    description="Multi-agent collaboration system using LangGraph, Redis, PostgreSQL, Celery, and FastAPI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes (both REST and WS)
app.include_router(router)
