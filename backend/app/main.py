"""FastAPI composition root. Run with: uvicorn app.main:app."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .repository import create_audit_schema, load_agent_profiles, load_agent_registry
from .routes import access, agents, codex, dashboard, missions


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    create_audit_schema()
    load_agent_registry()
    load_agent_profiles()
    yield


app = FastAPI(title="AgentOps API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

for router in (dashboard.router, access.router, codex.router, agents.router, missions.router):
    app.include_router(router)
