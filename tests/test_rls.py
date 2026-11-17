"""The database enforces tenant isolation on its own, as a second layer behind
the Python checks. These tests switch the Python checks off (or skip them by
querying directly) and show that the rows still stay hidden."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.tenant import BYPASS_KEY, set_tenant
from app.models import Application
from app.services import application_service


@pytest.fixture
def two_companies(
    make_recruiter: Callable,
    make_job: Callable,
    make_candidate: Callable,
    make_resume: Callable,
    make_application: Callable,
) -> dict:
    acme = make_recruiter("acme")
    globex = make_recruiter("globex")
    ana = make_candidate("ana")
    ben = make_candidate("ben")
    acme_app = make_application(ana, make_job(acme), make_resume(ana))
    globex_app = make_application(ben, make_job(globex), make_resume(ben))
    return {
        "acme": acme,
        "globex": globex,
        "ana": ana,
        "ben": ben,
        "acme_app": acme_app["id"],
        "globex_app": globex_app["id"],
    }


def visible_application_ids(
    db: Session, *, company_id: int | None = None, candidate_id: int | None = None
) -> set[int]:
    db.info[BYPASS_KEY] = False
    set_tenant(db, company_id=company_id, candidate_id=candidate_id)
    return set(db.scalars(select(Application.id)).all())


def test_a_recruiter_sees_only_their_companys_applications(
    db: Session, two_companies: dict
) -> None:
    ids = visible_application_ids(db, company_id=two_companies["acme"]["company_id"])

    assert ids == {two_companies["acme_app"]}


def test_a_candidate_sees_only_their_own_applications(
    db: Session, two_companies: dict
) -> None:
    ids = visible_application_ids(db, candidate_id=two_companies["ben"]["candidate_id"])

    assert ids == {two_companies["globex_app"]}


def test_without_a_tenant_no_application_is_visible(db: Session, two_companies: dict) -> None:
    assert visible_application_ids(db) == set()


def test_rls_blocks_a_leak_even_when_the_python_check_is_broken(
    client: TestClient, two_companies: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a future bug: the service forgets its permission check.
    monkeypatch.setattr(
        application_service.ApplicationService, "_can_view", lambda self, app, viewer: True
    )

    response = client.get(
        f"/applications/{two_companies['acme_app']}",
        headers=two_companies["globex"]["headers"],
    )

    assert response.status_code == 404  # the database never returned the row


def test_a_candidate_cannot_insert_an_application_for_someone_else(
    db: Session, two_companies: dict
) -> None:
    ana_app = db.get(Application, two_companies["acme_app"])
    assert ana_app is not None
    db.info[BYPASS_KEY] = False
    set_tenant(db, company_id=None, candidate_id=two_companies["ben"]["candidate_id"])

    with pytest.raises(DBAPIError, match="row-level security"), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO applications (job_id, candidate_id, resume_id, status) "
                "VALUES (:job, :candidate, :resume, 'applied')"
            ),
            {
                "job": ana_app.job_id,
                "candidate": ana_app.candidate_id,  # not Ben's id
                "resume": ana_app.resume_id,
            },
        )


def test_the_app_role_cannot_rewrite_the_audit_log(db: Session, two_companies: dict) -> None:
    db.info[BYPASS_KEY] = False
    set_tenant(db, company_id=two_companies["acme"]["company_id"], candidate_id=None)

    for statement in ("UPDATE audit_events SET action = 'x'", "DELETE FROM audit_events"):
        with pytest.raises(DBAPIError, match="permission denied"), db.begin_nested():
            db.execute(text(statement))


def test_requests_run_as_the_restricted_role(
    client: TestClient, db: Session, candidate: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    original = application_service.ApplicationService.list_for_candidate

    def spy(self: application_service.ApplicationService, candidate_id: int) -> list:
        seen.append(self.db.scalar(text("SELECT current_user")))
        return original(self, candidate_id)

    monkeypatch.setattr(application_service.ApplicationService, "list_for_candidate", spy)

    client.get("/me/applications", headers=candidate["headers"])

    assert seen == ["hiretrack_app"]
