from collections.abc import Callable

from fastapi.testclient import TestClient


def move(client: TestClient, application_id: int, user: dict, status: str):
    return client.patch(
        f"/applications/{application_id}/status",
        json={"status": status},
        headers=user["headers"],
    )


def test_apply_returns_201_in_applied_status(
    application: dict, candidate: dict, resume: dict
) -> None:
    assert application["status"] == "applied"
    assert application["candidate_id"] == candidate["candidate_id"]
    assert application["resume_id"] == resume["id"]


def test_cannot_apply_as_someone_else(
    client: TestClient, open_job: dict, candidate: dict, resume: dict, make_candidate: Callable
) -> None:
    victim = make_candidate("victim")

    # Extra fields such as candidate_id are ignored: identity comes from the token.
    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"resume_id": resume["id"], "candidate_id": victim["candidate_id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 201
    assert response.json()["candidate_id"] == candidate["candidate_id"]


def test_applying_twice_returns_409(
    client: TestClient, open_job: dict, candidate: dict, resume: dict, application: dict
) -> None:
    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"resume_id": resume["id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 409


def test_applying_to_a_draft_job_returns_404(
    client: TestClient, recruiter: dict, make_job: Callable, candidate: dict, resume: dict
) -> None:
    draft = make_job(recruiter, status="draft")

    response = client.post(
        f"/jobs/{draft['id']}/applications",
        json={"resume_id": resume["id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 404


def test_applying_to_a_missing_job_returns_404(
    client: TestClient, candidate: dict, resume: dict
) -> None:
    response = client.post(
        "/jobs/999999/applications",
        json={"resume_id": resume["id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 404


def test_applying_with_someone_elses_resume_returns_404(
    client: TestClient,
    open_job: dict,
    candidate: dict,
    make_candidate: Callable,
    make_resume: Callable,
) -> None:
    other = make_candidate("other")
    theirs = make_resume(other, name="Theirs", file_hash="c" * 64)

    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"resume_id": theirs["id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 404


def test_recruiter_cannot_apply(client: TestClient, open_job: dict, recruiter: dict) -> None:
    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"resume_id": 1},
        headers=recruiter["headers"],
    )

    assert response.status_code == 403


def test_application_keeps_its_resume_after_a_new_one_is_added(
    client: TestClient, candidate: dict, application: dict, make_resume: Callable
) -> None:
    make_resume(candidate, name="Backend Resume v2", file_hash="b" * 64)

    applications = client.get("/me/applications", headers=candidate["headers"]).json()

    assert applications[0]["resume"]["name"] == "Backend Resume v1"
    assert applications[0]["job"]["title"] == "Backend Engineer"


def test_full_hiring_flow(client: TestClient, recruiter: dict, application: dict) -> None:
    for status in ["screening", "interview", "offer", "hired"]:
        response = move(client, application["id"], recruiter, status)
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_skipping_stages_returns_409(
    client: TestClient, recruiter: dict, application: dict
) -> None:
    response = move(client, application["id"], recruiter, "hired")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"


def test_rejected_is_final(client: TestClient, recruiter: dict, application: dict) -> None:
    move(client, application["id"], recruiter, "rejected")

    assert move(client, application["id"], recruiter, "screening").status_code == 409


def test_same_status_twice_is_idempotent(
    client: TestClient, recruiter: dict, application: dict
) -> None:
    first = move(client, application["id"], recruiter, "screening")
    second = move(client, application["id"], recruiter, "screening")

    assert first.status_code == 200
    assert second.status_code == 200


def test_candidate_can_withdraw_during_interview(
    client: TestClient, recruiter: dict, candidate: dict, application: dict
) -> None:
    move(client, application["id"], recruiter, "screening")
    move(client, application["id"], recruiter, "interview")

    assert move(client, application["id"], candidate, "withdrawn").status_code == 200


def test_candidate_cannot_advance_their_own_application(
    client: TestClient, candidate: dict, application: dict
) -> None:
    assert move(client, application["id"], candidate, "screening").status_code == 403


def test_recruiter_cannot_withdraw_for_the_candidate(
    client: TestClient, recruiter: dict, application: dict
) -> None:
    assert move(client, application["id"], recruiter, "withdrawn").status_code == 403


def test_another_company_cannot_see_or_change_the_application(
    client: TestClient, application: dict, make_recruiter: Callable
) -> None:
    beta = make_recruiter("beta")

    assert client.get(f"/applications/{application['id']}", headers=beta["headers"]).status_code == 404
    assert move(client, application["id"], beta, "rejected").status_code == 404


def test_another_candidate_cannot_see_the_application(
    client: TestClient, application: dict, make_candidate: Callable
) -> None:
    other = make_candidate("other")

    response = client.get(f"/applications/{application['id']}", headers=other["headers"])

    assert response.status_code == 404


def test_recruiter_lists_applicants_for_their_own_job(
    client: TestClient, recruiter: dict, open_job: dict, application: dict
) -> None:
    response = client.get(f"/jobs/{open_job['id']}/applications", headers=recruiter["headers"])

    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [application["id"]]


def test_another_company_cannot_list_applicants(
    client: TestClient, open_job: dict, application: dict, make_recruiter: Callable
) -> None:
    beta = make_recruiter("beta")

    response = client.get(f"/jobs/{open_job['id']}/applications", headers=beta["headers"])

    assert response.status_code == 403


def test_changing_a_missing_application_returns_404(client: TestClient, recruiter: dict) -> None:
    assert move(client, 999999, recruiter, "screening").status_code == 404
