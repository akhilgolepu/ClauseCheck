from fastapi.testclient import TestClient

from api.main import app
from core.settings import Settings, get_settings


def test_health_is_live_even_when_database_is_unreachable() -> None:
    # Port 1 on localhost refuses connections immediately.
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql://nobody:nothing@127.0.0.1:1/none"
    )
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "unavailable"}
