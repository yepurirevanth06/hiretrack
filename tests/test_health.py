from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app


class BrokenSession:
    """A fake database session that fails like an unreachable database."""

    def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_is_down(client: TestClient) -> None:
    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
