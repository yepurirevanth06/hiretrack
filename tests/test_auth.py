from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import User

PASSWORD = "correct-horse-battery"


def register_candidate(client: TestClient, email: str = "priya@example.com"):
    return client.post(
        "/auth/register/candidate",
        json={"email": email, "password": PASSWORD, "full_name": "Priya"},
    )


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/auth/token", data={"username": email, "password": password})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_candidate_never_returns_the_password(client: TestClient) -> None:
    response = register_candidate(client)

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "candidate"
    assert isinstance(body["candidate_id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_password_is_stored_as_an_argon2_hash(client: TestClient, db: Session) -> None:
    register_candidate(client)

    user = db.scalar(select(User).where(User.email == "priya@example.com"))

    assert user is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_in_any_case_returns_409(client: TestClient) -> None:
    register_candidate(client)

    assert register_candidate(client, email="PRIYA@Example.com").status_code == 409


def test_short_password_returns_422(client: TestClient) -> None:
    response = client.post(
        "/auth/register/candidate",
        json={"email": "a@example.com", "password": "short", "full_name": "A"},
    )

    assert response.status_code == 422


def test_register_company_creates_company_and_recruiter(client: TestClient) -> None:
    response = client.post(
        "/auth/register/company",
        json={
            "company_name": "Acme Corp",
            "company_slug": "acme-corp",
            "email": "recruiter@acme.com",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "recruiter"
    company = client.get(f"/companies/{body['company_id']}").json()
    assert company["slug"] == "acme-corp"


def test_login_returns_a_bearer_token(client: TestClient) -> None:
    register_candidate(client)

    response = login(client, "priya@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_wrong_password_and_unknown_email_get_the_same_error(client: TestClient) -> None:
    register_candidate(client)

    wrong_password = login(client, "priya@example.com", "wrong-password-123")
    unknown_email = login(client, "nobody@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_returns_the_logged_in_user(client: TestClient) -> None:
    register_candidate(client)
    token = login(client, "priya@example.com").json()["access_token"]

    response = client.get("/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == "priya@example.com"


def test_token_signed_with_another_key_is_rejected(client: TestClient) -> None:
    user_id = register_candidate(client).json()["id"]
    forged = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "an-attackers-guessed-key",
        algorithm="HS256",
    )

    assert client.get("/auth/me", headers=auth_header(forged)).status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    user_id = register_candidate(client).json()["id"]
    expired = create_access_token(user_id, "candidate", expires_minutes=-1)

    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401
