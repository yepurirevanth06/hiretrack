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
    assert job["title"] == "Backend Engineer"
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
    response = client.post("/companies/999999/jobs", json=payload)

    assert response.status_code == 404


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
    response = client.get("/jobs/999999")

    assert response.status_code == 404


def test_list_jobs_filters_by_status(client: TestClient, company: dict[str, Any]) -> None:
    make_job(client, company["id"], title="Open 1", status="open")
    make_job(client, company["id"], title="Open 2", status="open")
    make_job(client, company["id"], title="Draft", status="draft")

    response = client.get("/jobs", params={"status": "open"})

    body = response.json()
    assert body["total"] == 2
    assert all(job["status"] == "open" for job in body["items"])


def test_list_jobs_filters_by_company(client: TestClient, company: dict[str, Any]) -> None:
    other = client.post("/companies", json={"name": "Beta", "slug": "beta"}).json()
    make_job(client, company["id"], title="Acme job")
    make_job(client, other["id"], title="Beta job")

    response = client.get("/jobs", params={"company_id": other["id"]})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Beta job"


def test_list_jobs_newest_first(client: TestClient, company: dict[str, Any]) -> None:
    first = make_job(client, company["id"], title="First")
    second = make_job(client, company["id"], title="Second")

    items = client.get("/jobs").json()["items"]

    assert [job["id"] for job in items] == [second["id"], first["id"]]


def test_list_jobs_pagination(client: TestClient, company: dict[str, Any]) -> None:
    for i in range(5):
        make_job(client, company["id"], title=f"Job {i}")

    page1 = client.get("/jobs", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/jobs", params={"limit": 2, "offset": 2}).json()
    page3 = client.get("/jobs", params={"limit": 2, "offset": 4}).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 1
    all_ids = [job["id"] for page in (page1, page2, page3) for job in page["items"]]
    assert len(set(all_ids)) == 5


def test_list_jobs_limit_above_100_returns_422(client: TestClient) -> None:
    response = client.get("/jobs", params={"limit": 101})

    assert response.status_code == 422
