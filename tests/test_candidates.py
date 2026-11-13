from typing import Any

from fastapi.testclient import TestClient


def test_create_candidate_stores_lowercase_email(client: TestClient) -> None:
    response = client.post(
        "/candidates", json={"email": "Priya@Example.COM", "full_name": "Priya"}
    )

    assert response.status_code == 201
    assert response.json()["email"] == "priya@example.com"


def test_duplicate_email_in_different_case_returns_409(
    client: TestClient, candidate: dict[str, Any]
) -> None:
    response = client.post(
        "/candidates", json={"email": "X@EXAMPLE.com", "full_name": "Someone"}
    )

    assert response.status_code == 409


def test_invalid_email_returns_422(client: TestClient) -> None:
    response = client.post("/candidates", json={"email": "not-an-email", "full_name": "A"})

    assert response.status_code == 422


def test_get_missing_candidate_returns_404(client: TestClient) -> None:
    assert client.get("/candidates/999999").status_code == 404


def test_add_resume_returns_201(client: TestClient, resume: dict[str, Any]) -> None:
    assert resume["name"] == "Backend Resume v1"


def test_same_resume_file_twice_returns_409(
    client: TestClient, candidate: dict[str, Any], resume: dict[str, Any]
) -> None:
    response = client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={"name": "Copy", "file_key": "resumes/x/copy.pdf", "file_hash": "a" * 64},
    )

    assert response.status_code == 409


def test_list_resumes_newest_first(
    client: TestClient, candidate: dict[str, Any], resume: dict[str, Any]
) -> None:
    newer = client.post(
        f"/candidates/{candidate['id']}/resumes",
        json={"name": "v2", "file_key": "resumes/x/v2.pdf", "file_hash": "b" * 64},
    ).json()

    names = [r["name"] for r in client.get(f"/candidates/{candidate['id']}/resumes").json()]

    assert names == [newer["name"], resume["name"]]
