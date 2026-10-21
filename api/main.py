"""FastAPI app. Phase 0 exposes only the liveness endpoint."""

from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI

from core.settings import Settings, get_settings

app = FastAPI(
    title="ClauseCheck",
    version="0.1.0",
    description="Research prototype. Not compliance advice.",
)


def _database_status(database_url: str) -> str:
    try:
        with psycopg.connect(database_url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        return "unavailable"
    return "ok"


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    # Liveness stays 200 when the database is down; the field reports it separately.
    return {"status": "ok", "database": _database_status(settings.database_url)}
