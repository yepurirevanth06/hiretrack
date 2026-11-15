from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

JOB = {
    "title": "Backend Engineer",
    "description": "Build APIs",
    "location": "Remote",
    "employment_type": "full_time",
}


def test_recruiter_can_create_a_job(recruiter: dict, make_job: Callable) -> None:
    job = make_job(recruiter)

    assert job["company_id"] == recruiter["company_id"]
    assert job["status"] == "open"


def test_new_job_defaults_to_draft(client: TestClient, recruiter: dict) -> None:
    response = client.post(
        f"/companies/{recruiter['company_id']}/jobs", json=JOB, headers=recruiter["headers"]
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_creating_a_job_requires_login(client: TestClient, recruiter: dict) -> None:
    response = client.post(f"/companies/{recruiter['company_id']}/jobs", json=JOB)

    assert response.status_code == 401


def test_candidate_cannot_create_a_job(
    client: TestClient, recruiter: dict, candidate: dict
) -> None:
    response = client.post(
        f"/companies/{recruiter['company_id']}/jobs", json=JOB, headers=candidate["headers"]
    )

    assert response.status_code == 403


def test_recruiter_cannot_post_for_another_company(
    client: TestClient, recruiter: dict, make_recruiter: Callable
) -> None:
    beta = make_recruiter("beta")

    response = client.post(
        f"/companies/{recruiter['company_id']}/jobs", json=JOB, headers=beta["headers"]
    )

    assert response.status_code == 403


def test_posting_to_a_missing_company_returns_404(client: TestClient, recruiter: dict) -> None:
    response = client.post("/companies/999999/jobs", json=JOB, headers=recruiter["headers"])

    assert response.status_code == 404


def test_invalid_employment_type_returns_422(client: TestClient, recruiter: dict) -> None:
    response = client.post(
        f"/companies/{recruiter['company_id']}/jobs",
        json={**JOB, "employment_type": "freelance"},
        headers=recruiter["headers"],
    )

    assert response.status_code == 422


def test_open_job_is_public(client: TestClient, recruiter: dict, make_job: Callable) -> None:
    job = make_job(recruiter)

    assert client.get(f"/jobs/{job['id']}").status_code == 200


def test_draft_job_is_hidden_from_everyone_but_its_company(
    client: TestClient, recruiter: dict, make_recruiter: Callable, make_job: Callable
) -> None:
    draft = make_job(recruiter, status="draft")
    beta = make_recruiter("beta")

    assert client.get(f"/jobs/{draft['id']}").status_code == 404
    assert client.get(f"/jobs/{draft['id']}", headers=beta["headers"]).status_code == 404
    assert client.get(f"/jobs/{draft['id']}", headers=recruiter["headers"]).status_code == 200


def test_missing_job_returns_404(client: TestClient) -> None:
    assert client.get("/jobs/999999").status_code == 404


def test_public_listing_shows_only_open_jobs(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    make_job(recruiter, title="Open")
    make_job(recruiter, title="Draft", status="draft")

    items = client.get("/jobs").json()["items"]

    assert [job["title"] for job in items] == ["Open"]


def test_outsiders_cannot_list_drafts_by_filtering(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    make_job(recruiter, status="draft")

    assert client.get("/jobs", params={"status": "draft"}).json()["items"] == []


def test_recruiter_sees_own_company_drafts(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    make_job(recruiter, title="Draft", status="draft")

    items = client.get(
        "/jobs",
        params={"company_id": recruiter["company_id"], "status": "draft"},
        headers=recruiter["headers"],
    ).json()["items"]

    assert [job["title"] for job in items] == ["Draft"]


def test_recruiter_cannot_see_another_companys_drafts(
    client: TestClient, recruiter: dict, make_recruiter: Callable, make_job: Callable
) -> None:
    make_job(recruiter, status="draft")
    beta = make_recruiter("beta")

    items = client.get(
        "/jobs",
        params={"company_id": recruiter["company_id"], "status": "draft"},
        headers=beta["headers"],
    ).json()["items"]

    assert items == []


def test_list_jobs_filters_by_company(
    client: TestClient, recruiter: dict, make_recruiter: Callable, make_job: Callable
) -> None:
    beta = make_recruiter("beta")
    make_job(recruiter, title="Acme job")
    make_job(beta, title="Beta job")

    items = client.get("/jobs", params={"company_id": beta["company_id"]}).json()["items"]

    assert [job["title"] for job in items] == ["Beta job"]


def test_list_jobs_newest_first(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    first = make_job(recruiter, title="First")
    second = make_job(recruiter, title="Second")

    items = client.get("/jobs").json()["items"]

    assert [job["id"] for job in items] == [second["id"], first["id"]]


def test_cursor_pagination_returns_every_job_exactly_once(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    created_ids = [make_job(recruiter, title=f"Job {i}")["id"] for i in range(5)]

    seen: list[int] = []
    pages = 0
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/jobs", params=params).json()
        seen.extend(job["id"] for job in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert pages == 3
    assert seen == sorted(created_ids, reverse=True)


def test_next_cursor_is_none_on_the_last_page(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    make_job(recruiter)

    assert client.get("/jobs", params={"limit": 10}).json()["next_cursor"] is None


def test_new_job_while_paging_causes_no_duplicates(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    for i in range(4):
        make_job(recruiter, title=f"Job {i}")

    page1 = client.get("/jobs", params={"limit": 2}).json()
    make_job(recruiter, title="Posted while paging")
    page2 = client.get("/jobs", params={"limit": 2, "cursor": page1["next_cursor"]}).json()

    page1_ids = {job["id"] for job in page1["items"]}
    page2_ids = {job["id"] for job in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page2_ids) == 2


def test_total_is_only_computed_when_requested(
    client: TestClient, recruiter: dict, make_job: Callable
) -> None:
    for i in range(3):
        make_job(recruiter, title=f"Job {i}")

    assert client.get("/jobs").json()["total"] is None
    assert client.get("/jobs", params={"include_total": True}).json()["total"] == 3


def test_invalid_cursor_returns_400(client: TestClient) -> None:
    response = client.get("/jobs", params={"cursor": "not-a-real-cursor"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_list_jobs_limit_above_100_returns_422(client: TestClient) -> None:
    assert client.get("/jobs", params={"limit": 101}).status_code == 422
