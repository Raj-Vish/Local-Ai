"""Expense Management API.

Phase one: authentication, documents, expenses and reports. No AI yet —
see the architecture blueprint for what plugs in later and where.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import models  # noqa: F401  -- imported so Base knows about every table
from config import settings
from database import Base, engine

log = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates any table that does not exist yet. It does NOT alter existing
    # tables: change a column and nothing happens here, so during prototyping
    # drop the table and let it rebuild. Alembic handles this properly once
    # the schema stops moving.
    Base.metadata.create_all(bind=engine)
    log.info("tables ready: %s", ", ".join(sorted(Base.metadata.tables)))
    yield


app = FastAPI(
    title="Expense Management API",
    description="AI-Assisted Enterprise Expense Management System",
    version="0.2.0",
    lifespan=lifespan,
)

# The browser blocks a response from a different origin unless the server
# explicitly allows it. React runs on 5173, this API on 8000 — different ports
# count as different origins, so without this every fetch fails.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    """Liveness check for the API and its database.

    Reports "degraded" rather than failing when MySQL is unreachable, so the
    frontend can tell "the server is down" apart from "the database is down".
    """
    database = "up"
    detail = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        database = "down"
        detail = type(exc).__name__
        log.warning("health check: database unreachable (%s)", detail)

    return {
        "status": "ok" if database == "up" else "degraded",
        "api": "up",
        "database": database,
        "detail": detail,
        "version": app.version,
    }
