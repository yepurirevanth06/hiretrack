from fastapi.testclient import TestClient


def new_application(client: TestClient, job_id: int, n: int) -> int:
    candidate = client.post(
        "/candidates", json={"email": f"c{n}@example.com", "full_name": f"Candidate {n}"}
    ).json()
    resume = client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={"name": "CV", "file_key": f"resumes/{n}.pdf", "file_hash": f"{n:064x}"},
    ).json()
    application = client.post(
        f"/jobs/{job_id}/applications",
        json={"candidate_id": candidate["id"], "resume_id": resume["id"]},
    ).json()
    return application["id"]


def move(client: TestClient, application_id: int, *statuses: str) -> None:
    for status in statuses:
        response = client.patch(
            f"/applications/{application_id}/status", json={"status": status}
        )
        assert response.status_code == 200, response.text


def test_closing_job_rejects_only_active_applications(
    client: TestClient, open_job: dict
) -> None:
    applied = new_application(client, open_job["id"], 1)
    interviewing = new_application(client, open_job["id"], 2)
    move(client, interviewing, "screening", "interview")
    hired = new_application(client, open_job["id"], 3)
    move(client, hired, "screening", "interview", "offer", "hired")
    withdrawn = new_application(client, open_job["id"], 4)
    move(client, withdrawn, "withdrawn")

    response = client.post(f"/jobs/{open_job['id']}/close")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "closed"
    assert body["rejected_applications"] == 2

    statuses = {
        app_id: client.get(f"/applications/{app_id}").json()["status"]
        for app_id in (applied, interviewing, hired, withdrawn)
    }
    assert statuses == {
        applied: "rejected",
        interviewing: "rejected",
        hired: "hired",
        withdrawn: "withdrawn",
    }


def test_closing_twice_is_idempotent(client: TestClient, open_job: dict) -> None:
    new_application(client, open_job["id"], 1)
    client.post(f"/jobs/{open_job['id']}/close")

    response = client.post(f"/jobs/{open_job['id']}/close")

    assert response.status_code == 200
    assert response.json()["rejected_applications"] == 0


def test_cannot_apply_after_job_is_closed(client: TestClient, open_job: dict) -> None:
    client.post(f"/jobs/{open_job['id']}/close")

    candidate = client.post(
        "/candidates", json={"email": "late@example.com", "full_name": "Late"}
    ).json()
    resume = client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={"name": "CV", "file_key": "resumes/late.pdf", "file_hash": "d" * 64},
    ).json()
    response = client.post(
        f"/jobs/{open_job['id']}/applications",
        json={"candidate_id": candidate["id"], "resume_id": resume["id"]},
    )

    assert response.status_code == 409


def test_closing_missing_job_returns_404(client: TestClient) -> None:
    assert client.post("/jobs/999999/close").status_code == 404
