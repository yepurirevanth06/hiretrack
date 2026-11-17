from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models
from app.core import security
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.db.tenant import BYPASS_KEY, TENANT_KEY, reapply
from app.main import app

# Argon2 is deliberately slow. Tests use the cheapest valid settings so the
# suite stays fast. Never do this outside tests.
security.password_hasher = PasswordHash(
    (Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1),)
)

TEST_PASSWORD = "correct-horse-battery"
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
    # Test code reads the database as the superuser, so assertions can see
    # every row. Requests made through `client` run under RLS, like production.
    session.info[BYPASS_KEY] = True
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db.info[BYPASS_KEY] = False
        reapply(db)
        try:
            yield db
        finally:
            # Like the real get_db: whatever a request didn't commit, even when
            # it fails with an error, is thrown away.
            db.rollback()
            db.info.pop(TENANT_KEY, None)
            db.info[BYPASS_KEY] = True

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(user: dict[str, Any]) -> dict[str, str]:
    token = create_access_token(user["id"], user["role"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_recruiter(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _make(slug: str = "acme-corp") -> dict[str, Any]:
        response = client.post(
            "/auth/register/company",
            json={
                "company_name": slug.replace("-", " ").title(),
                "company_slug": slug,
                "email": f"recruiter@{slug}.com",
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 201, response.text
        user = response.json()
        return {**user, "headers": auth_headers(user)}

    return _make


@pytest.fixture
def make_candidate(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _make(name: str = "x") -> dict[str, Any]:
        response = client.post(
            "/auth/register/candidate",
            json={
                "email": f"{name}@example.com",
                "password": TEST_PASSWORD,
                "full_name": f"Candidate {name}",
            },
        )
        assert response.status_code == 201, response.text
        user = response.json()
        return {**user, "headers": auth_headers(user)}

    return _make


@pytest.fixture
def make_job(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _make(recruiter: dict[str, Any], **overrides: Any) -> dict[str, Any]:
        payload = {
            "title": "Backend Engineer",
            "description": "Build APIs with Python",
            "location": "Remote",
            "employment_type": "full_time",
            "status": "open",
        }
        payload.update(overrides)
        response = client.post(
            f"/companies/{recruiter['company_id']}/jobs",
            json=payload,
            headers=recruiter["headers"],
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def make_resume(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _make(
        candidate: dict[str, Any], name: str = "Backend Resume v1", file_hash: str = "a" * 64
    ) -> dict[str, Any]:
        response = client.post(
            "/me/resumes",
            json={
                "name": name,
                "file_key": f"resumes/{candidate['candidate_id']}/{file_hash[:8]}.pdf",
                "file_hash": file_hash,
            },
            headers=candidate["headers"],
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def make_application(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _make(
        candidate: dict[str, Any], job: dict[str, Any], resume: dict[str, Any]
    ) -> dict[str, Any]:
        response = client.post(
            f"/jobs/{job['id']}/applications",
            json={"resume_id": resume["id"]},
            headers=candidate["headers"],
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def recruiter(make_recruiter: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    return make_recruiter("acme-corp")


@pytest.fixture
def open_job(
    make_job: Callable[..., dict[str, Any]], recruiter: dict[str, Any]
) -> dict[str, Any]:
    return make_job(recruiter)


@pytest.fixture
def candidate(make_candidate: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    return make_candidate("x")


@pytest.fixture
def resume(
    make_resume: Callable[..., dict[str, Any]], candidate: dict[str, Any]
) -> dict[str, Any]:
    return make_resume(candidate)


@pytest.fixture
def application(
    make_application: Callable[..., dict[str, Any]],
    candidate: dict[str, Any],
    open_job: dict[str, Any],
    resume: dict[str, Any],
) -> dict[str, Any]:
    return make_application(candidate, open_job, resume)


@pytest.fixture
def query_counter(db: Session) -> Iterator[dict[str, int]]:
    from sqlalchemy import event

    counter = {"selects": 0}

    def count_selects(conn, cursor, statement, parameters, context, executemany) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            counter["selects"] += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    yield counter
    event.remove(engine, "before_cursor_execute", count_selects)
