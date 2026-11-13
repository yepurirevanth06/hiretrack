from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = make_url(settings.database_url).set(database="hiretrack_test")
engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def create_schema() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def company(client: TestClient) -> dict[str, Any]:
    response = client.post("/companies", json={"name": "Acme Corp", "slug": "acme-corp"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def open_job(client: TestClient, company: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "title": "Backend Engineer",
        "description": "Build APIs with Python",
        "location": "Remote",
        "employment_type": "full_time",
        "status": "open",
    }
    response = client.post(f"/companies/{company['id']}/jobs", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def candidate(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/candidates", json={"email": "x@example.com", "full_name": "Candidate X"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def resume(client: TestClient, candidate: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={
            "name": "Backend Resume v1",
            "file_key": "resumes/x/v1.pdf",
            "file_hash": "a" * 64,
        },
    )
    assert response.status_code == 201
    return response.json()
