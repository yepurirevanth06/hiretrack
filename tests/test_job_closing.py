from collections.abc import Callable

from fastapi.testclient import TestClient


def move(client: TestClient, application_id: int, user: dict, *statuses: str) -> None:
    for status in statuses:
        response = client.patch(
            f"/applications/{application_id}/status",
            json={"status": status},
            headers=user["headers"],
        )
        assert response.status_code == 200, response.text


def test_closing_a_job_rejects_only_active_applications(
    client: TestClient,
    recruiter: dict,
    open_job: dict,
    make_candidate: Callable,
    make_resume: Callable,
    make_application: Callable,
) -> None:
    def apply(name: str) -> tuple[dict, int]:
        candidate = make_candidate(name)
        resume = make_resume(candidate)
        return candidate, make_application(candidate, open_job, resume)["id"]

    _, applied = apply("c1")
    _, interviewing = apply("c2")
    move(client, interviewing, recruiter, "screening", "interview")
    _, hired = apply("c3")
    move(client, hired, recruiter, "screening", "interview", "offer", "hired")
    c4, withdrawn = apply("c4")
    move(client, withdrawn, c4, "withdrawn")

    response = client.post(f"/jobs/{open_job['id']}/close", headers=recruiter["headers"])

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "closed"
    assert response.json()["rejected_applications"] == 2

    statuses = {
        app_id: client.get(f"/applications/{app_id}", headers=recruiter["headers"]).json()["status"]
        for app_id in (applied, interviewing, hired, withdrawn)
    }
    assert statuses == {
        applied: "rejected",
        interviewing: "rejected",
        hired: "hired",
        withdrawn: "withdrawn",
    }


def test_closing_twice_is_idempotent(
    client: TestClient, recruiter: dict, open_job: dict, application: dict
) -> None:
    client.post(f"/jobs/{open_job['id']}/close", headers=recruiter["headers"])

    response = client.post(f"/jobs/{open_job['id']}/close", headers=recruiter["headers"])

    assert response.status_code == 200
    assert response.json()["rejected_applications"] == 0


def test_cannot_apply_after_the_job_is_closed(
    client: TestClient, recruiter: dict, open_job: dict, candidate: dict, resume: dict
) -> None:
    client.post(f"/jobs/{open_job['id']}/close", headers=recruiter["headers"])

    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"resume_id": resume["id"]},
        headers=candidate["headers"],
    )

    assert response.status_code == 404


def test_closing_a_missing_job_returns_404(client: TestClient, recruiter: dict) -> None:
    assert client.post("/jobs/999999/close", headers=recruiter["headers"]).status_code == 404


def test_another_company_cannot_close_the_job(
    client: TestClient, open_job: dict, make_recruiter: Callable
) -> None:
    beta = make_recruiter("beta")

    response = client.post(f"/jobs/{open_job['id']}/close", headers=beta["headers"])

    assert response.status_code == 403


def test_candidate_cannot_close_a_job(
    client: TestClient, open_job: dict, candidate: dict
) -> None:
    response = client.post(f"/jobs/{open_job['id']}/close", headers=candidate["headers"])

    assert response.status_code == 403
