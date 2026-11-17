from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import Application, AuditEvent
from app.repositories.audit_repository import AuditRepository


def set_status(client: TestClient, application_id: int, user: dict, status: str):
    return client.patch(
        f"/applications/{application_id}/status",
        json={"status": status},
        headers=user["headers"],
    )


def events_for(db: Session, entity_type: str, entity_id: int) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.id)
        ).all()
    )


def test_applying_records_a_created_event(
    db: Session, candidate: dict, application: dict
) -> None:
    [event] = events_for(db, "application", application["id"])

    assert event.action == "application.created"
    assert event.actor_user_id == candidate["id"]


def test_status_change_records_who_changed_what(
    client: TestClient, db: Session, recruiter: dict, application: dict
) -> None:
    set_status(client, application["id"], recruiter, "screening")

    event = events_for(db, "application", application["id"])[-1]
    assert event.action == "application.status_changed"
    assert event.actor_user_id == recruiter["id"]
    assert event.details == {"from": "applied", "to": "screening"}


def test_no_op_and_rejected_changes_are_not_recorded(
    client: TestClient, db: Session, candidate: dict, application: dict
) -> None:
    set_status(client, application["id"], candidate, "screening")  # 403
    set_status(client, application["id"], candidate, "withdrawn")  # 200
    set_status(client, application["id"], candidate, "withdrawn")  # no-op

    actions = [e.action for e in events_for(db, "application", application["id"])]
    assert actions == ["application.created", "application.status_changed"]


def test_if_the_audit_write_fails_the_status_change_is_rolled_back_too(
    client: TestClient,
    db: Session,
    recruiter: dict,
    application: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_record(self: AuditRepository, **kwargs: Any) -> None:
        raise RuntimeError("audit storage is down")

    monkeypatch.setattr(AuditRepository, "record", broken_record)

    with pytest.raises(RuntimeError):
        set_status(client, application["id"], recruiter, "screening")

    stored = db.get(Application, application["id"])
    assert stored is not None
    assert stored.status == "applied"  # no change without its audit row


def test_history_shows_the_timeline_in_order(
    client: TestClient, candidate: dict, recruiter: dict, application: dict
) -> None:
    set_status(client, application["id"], recruiter, "screening")
    set_status(client, application["id"], recruiter, "interview")

    response = client.get(
        f"/applications/{application['id']}/history", headers=candidate["headers"]
    )

    assert response.status_code == 200
    assert [(e["action"], e["details"].get("to")) for e in response.json()] == [
        ("application.created", "applied"),
        ("application.status_changed", "screening"),
        ("application.status_changed", "interview"),
    ]


def test_history_follows_the_same_visibility_rules(
    client: TestClient, make_candidate: Callable, application: dict
) -> None:
    stranger = make_candidate("stranger")

    response = client.get(
        f"/applications/{application['id']}/history", headers=stranger["headers"]
    )

    assert response.status_code == 404


def test_closing_a_job_records_the_job_and_each_rejection(
    client: TestClient, db: Session, recruiter: dict, open_job: dict, application: dict
) -> None:
    client.post(f"/jobs/{open_job['id']}/close", headers=recruiter["headers"])

    [job_event] = events_for(db, "job", open_job["id"])
    assert job_event.action == "job.closed"
    assert job_event.details == {"rejected_applications": 1}

    last = events_for(db, "application", application["id"])[-1]
    assert last.details == {"to": "rejected", "reason": "job_closed"}


def test_audit_rows_cannot_be_updated_or_deleted(db: Session, application: dict) -> None:
    for statement in ("UPDATE audit_events SET action = 'tampered'", "DELETE FROM audit_events"):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement))
