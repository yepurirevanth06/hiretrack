from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_refresh_token
from app.models import AuditEvent, RefreshToken, User
from tests.conftest import TEST_PASSWORD


def login(client: TestClient, user: dict[str, Any]) -> dict[str, str]:
    response = client.post(
        "/auth/token", data={"username": user["email"], "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


def refresh(client: TestClient, refresh_token: str):
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_login_returns_an_access_and_a_refresh_token(
    client: TestClient, candidate: dict
) -> None:
    tokens = login(client, candidate)

    assert tokens["access_token"].count(".") == 2  # a JWT
    assert tokens["refresh_token"].count(".") == 0  # an opaque random string
    assert tokens["token_type"] == "bearer"


def test_only_a_hash_of_the_refresh_token_is_stored(
    client: TestClient, db: Session, candidate: dict
) -> None:
    raw = login(client, candidate)["refresh_token"]

    stored = db.scalars(select(RefreshToken.token_hash)).all()

    assert raw not in stored
    assert hash_refresh_token(raw) in stored


def test_refresh_returns_a_new_working_pair(client: TestClient, candidate: dict) -> None:
    first = login(client, candidate)

    response = refresh(client, first["refresh_token"])

    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert client.get("/auth/me", headers=bearer(second["access_token"])).status_code == 200


def test_unknown_refresh_token_is_rejected(client: TestClient) -> None:
    response = refresh(client, "not-a-real-token")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_reusing_a_rotated_token_revokes_the_whole_session(
    client: TestClient, candidate: dict
) -> None:
    stolen = login(client, candidate)["refresh_token"]
    current = refresh(client, stolen).json()["refresh_token"]  # real user rotates

    assert refresh(client, stolen).status_code == 401  # attacker replays the old one
    assert refresh(client, current).status_code == 401  # whole family is now dead


def test_reuse_in_one_session_does_not_log_out_other_devices(
    client: TestClient, candidate: dict
) -> None:
    laptop = login(client, candidate)["refresh_token"]
    phone = login(client, candidate)["refresh_token"]
    refresh(client, laptop)

    refresh(client, laptop)  # reuse on the laptop session

    assert refresh(client, phone).status_code == 200


def test_reuse_is_written_to_the_audit_log(
    client: TestClient, db: Session, candidate: dict
) -> None:
    token = login(client, candidate)["refresh_token"]
    refresh(client, token)

    refresh(client, token)

    actions = db.scalars(
        select(AuditEvent.action).where(AuditEvent.actor_user_id == candidate["id"])
    ).all()
    assert "auth.refresh_token_reused" in actions


def test_expired_refresh_token_is_rejected(
    client: TestClient, db: Session, candidate: dict
) -> None:
    raw = login(client, candidate)["refresh_token"]
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    )
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()

    assert refresh(client, raw).status_code == 401


def test_deactivated_user_cannot_refresh(
    client: TestClient, db: Session, candidate: dict
) -> None:
    raw = login(client, candidate)["refresh_token"]
    user = db.get(User, candidate["id"])
    assert user is not None
    user.is_active = False
    db.flush()

    assert refresh(client, raw).status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient, candidate: dict) -> None:
    raw = login(client, candidate)["refresh_token"]

    response = client.post("/auth/logout", json={"refresh_token": raw})

    assert response.status_code == 204
    assert refresh(client, raw).status_code == 401


def test_logout_with_an_unknown_token_still_returns_204(client: TestClient) -> None:
    response = client.post("/auth/logout", json={"refresh_token": "never-issued"})

    assert response.status_code == 204


def test_logout_all_ends_every_session(client: TestClient, candidate: dict) -> None:
    laptop = login(client, candidate)
    phone = login(client, candidate)

    response = client.post("/auth/logout-all", headers=bearer(laptop["access_token"]))

    assert response.status_code == 204
    assert refresh(client, laptop["refresh_token"]).status_code == 401
    assert refresh(client, phone["refresh_token"]).status_code == 401


def test_logout_all_requires_authentication(client: TestClient) -> None:
    assert client.post("/auth/logout-all").status_code == 401


def test_logout_all_only_affects_the_caller(
    client: TestClient, make_candidate: Any
) -> None:
    alice = make_candidate("alice")
    bob = make_candidate("bob")
    alice_tokens = login(client, alice)
    bob_tokens = login(client, bob)

    client.post("/auth/logout-all", headers=bearer(alice_tokens["access_token"]))

    assert refresh(client, bob_tokens["refresh_token"]).status_code == 200
