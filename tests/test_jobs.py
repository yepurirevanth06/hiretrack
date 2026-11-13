from typing import Any

from fastapi.testclient import TestClient


def make_job(client: TestClient, company_id: int, **overrides: Any) -> dict[str, Any]:
    payload = {
        "title": "Backend Engineer",
        "description": "Build APIs with Python",
        "location": "Remote",
        "employment_type": "full_time",
        "status": "open",
    }
    payload.update(overrides)
    response = client.post(f"/companies/{company_id}/jobs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_job_returns_201(client: TestClient, company: dict[str, Any]) -> None:
    job = make_job(client, company["id"])

    assert job["company_id"] == company["id"]
    assert job["status"] == "open"


def test_new_job_defaults_to_draft(client: TestClient, company: dict[str, Any]) -> None:
    payload = {
        "title": "Data Engineer",
        "description": "Pipelines",
        "location": "Fairfax, VA",
        "employment_type": "full_time",
    }
    response = client.post(f"/companies/{company['id']}/jobs", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_create_job_for_missing_company_returns_404(client: TestClient) -> None:
    payload = {
        "title": "Ghost Job",
        "description": "No company",
        "location": "Remote",
        "employment_type": "full_time",
    }
    assert client.post("/companies/999999/jobs", json=payload).status_code == 404


def test_invalid_employment_type_returns_422(client: TestClient, company: dict[str, Any]) -> None:
    payload = {
        "title": "Test",
        "description": "Test",
        "location": "Remote",
        "employment_type": "freelance",
    }
    response = client.post(f"/companies/{company['id']}/jobs", json=payload)

    assert response.status_code == 422


def test_get_job_returns_200(client: TestClient, company: dict[str, Any]) -> None:
    job = make_job(client, company["id"])

    response = client.get(f"/jobs/{job['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == job["id"]


def test_get_missing_job_returns_404(client: TestClient) -> None:
    assert client.get("/jobs/999999").status_code == 404


def test_list_jobs_filters_by_status(client: TestClient, company: dict[str, Any]) -> None:
    make_job(client, company["id"], title="Open 1", status="open")
    make_job(client, company["id"], title="Open 2", status="open")
    make_job(client, company["id"], title="Draft", status="draft")

    items = client.get("/jobs", params={"status": "open"}).json()["items"]

    assert len(items) == 2
    assert all(job["status"] == "open" for job in items)


def test_list_jobs_filters_by_company(client: TestClient, company: dict[str, Any]) -> None:
    other = client.post("/companies", json={"name": "Beta", "slug": "beta"}).json()
    make_job(client, company["id"], title="Acme job")
    make_job(client, other["id"], title="Beta job")

    items = client.get("/jobs", params={"company_id": other["id"]}).json()["items"]

    assert [job["title"] for job in items] == ["Beta job"]


def test_list_jobs_newest_first(client: TestClient, company: dict[str, Any]) -> None:
    first = make_job(client, company["id"], title="First")
    second = make_job(client, company["id"], title="Second")

    items = client.get("/jobs").json()["items"]

    assert [job["id"] for job in items] == [second["id"], first["id"]]


def test_cursor_pagination_returns_every_job_exactly_once(
    client: TestClient, company: dict[str, Any]
) -> None:
    created_ids = [make_job(client, company["id"], title=f"Job {i}")["id"] for i in range(5)]

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


def test_next_cursor_is_none_on_the_last_page(client: TestClient, company: dict[str, Any]) -> None:
    make_job(client, company["id"])

    assert client.get("/jobs", params={"limit": 10}).json()["next_cursor"] is None


def test_new_job_while_paging_causes_no_duplicates(
    client: TestClient, company: dict[str, Any]
) -> None:
    for i in range(4):
        make_job(client, company["id"], title=f"Job {i}")

    page1 = client.get("/jobs", params={"limit": 2}).json()
    make_job(client, company["id"], title="Posted while paging")
    page2 = client.get("/jobs", params={"limit": 2, "cursor": page1["next_cursor"]}).json()

    page1_ids = {job["id"] for job in page1["items"]}
    page2_ids = {job["id"] for job in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page2_ids) == 2


def test_total_is_only_computed_when_requested(
    client: TestClient, company: dict[str, Any]
) -> None:
    for i in range(3):
        make_job(client, company["id"], title=f"Job {i}")

    assert client.get("/jobs").json()["total"] is None
    assert client.get("/jobs", params={"include_total": True}).json()["total"] == 3


def test_invalid_cursor_returns_400(client: TestClient) -> None:
    response = client.get("/jobs", params={"cursor": "not-a-real-cursor"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_list_jobs_limit_above_100_returns_422(client: TestClient) -> None:
    assert client.get("/jobs", params={"limit": 101}).status_code == 422
