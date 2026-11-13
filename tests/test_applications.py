from typing import Any

from fastapi.testclient import TestClient


def apply(client: TestClient, job_id: int, candidate_id: int, resume_id: int):
    return client.post(
        f"/jobs/{job_id}/applications",
        json={"candidate_id": candidate_id, "resume_id": resume_id},
    )


def move(client: TestClient, application_id: int, status: str):
    return client.patch(f"/applications/{application_id}/status", json={"status": status})


def test_apply_returns_201_in_applied_status(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    response = apply(client, open_job["id"], candidate["id"], resume["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "applied"
    assert body["resume_id"] == resume["id"]


def test_applying_twice_returns_409(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    apply(client, open_job["id"], candidate["id"], resume["id"])

    response = apply(client, open_job["id"], candidate["id"], resume["id"])

    assert response.status_code == 409


def test_applying_to_draft_job_returns_409(
    client: TestClient, company: dict, candidate: dict, resume: dict
) -> None:
    draft = client.post(
        f"/companies/{company['id']}/jobs",
        json={
            "title": "Secret Role",
            "description": "Not public yet",
            "location": "Remote",
            "employment_type": "full_time",
            "status": "draft",
        },
    ).json()

    response = apply(client, draft["id"], candidate["id"], resume["id"])

    assert response.status_code == 409


def test_applying_to_missing_job_returns_404(
    client: TestClient, candidate: dict, resume: dict
) -> None:
    assert apply(client, 999999, candidate["id"], resume["id"]).status_code == 404


def test_applying_with_someone_elses_resume_returns_404(
    client: TestClient, open_job: dict, candidate: dict
) -> None:
    other = client.post(
        "/candidates", json={"email": "other@example.com", "full_name": "Other"}
    ).json()
    other_resume = client.post(
        f"/candidates/{other['id']}/resumes",
        json={"name": "Theirs", "file_key": "resumes/o/1.pdf", "file_hash": "c" * 64},
    ).json()

    response = apply(client, open_job["id"], candidate["id"], other_resume["id"])

    assert response.status_code == 404


def test_application_keeps_its_resume_after_a_new_one_is_added(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    apply(client, open_job["id"], candidate["id"], resume["id"])
    client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={"name": "Backend Resume v2", "file_key": "resumes/x/v2.pdf", "file_hash": "b" * 64},
    )

    applications = client.get(f"/candidates/{candidate['id']}/applications").json()

    assert applications[0]["resume"]["name"] == "Backend Resume v1"
    assert applications[0]["job"]["title"] == "Backend Engineer"


def test_full_hiring_flow(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    application = apply(client, open_job["id"], candidate["id"], resume["id"]).json()

    for status in ["screening", "interview", "offer", "hired"]:
        response = move(client, application["id"], status)
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_skipping_stages_returns_409(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    application = apply(client, open_job["id"], candidate["id"], resume["id"]).json()

    response = move(client, application["id"], "hired")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"


def test_rejected_is_final(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    application = apply(client, open_job["id"], candidate["id"], resume["id"]).json()
    move(client, application["id"], "rejected")

    assert move(client, application["id"], "screening").status_code == 409


def test_same_status_twice_is_idempotent(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    application = apply(client, open_job["id"], candidate["id"], resume["id"]).json()

    first = move(client, application["id"], "screening")
    second = move(client, application["id"], "screening")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "screening"


def test_candidate_can_withdraw_during_interview(
    client: TestClient, open_job: dict, candidate: dict, resume: dict
) -> None:
    application = apply(client, open_job["id"], candidate["id"], resume["id"]).json()
    move(client, application["id"], "screening")
    move(client, application["id"], "interview")

    assert move(client, application["id"], "withdrawn").status_code == 200


def test_changing_missing_application_returns_404(client: TestClient) -> None:
    assert move(client, 999999, "screening").status_code == 404
