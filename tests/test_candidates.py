from collections.abc import Callable

from fastapi.testclient import TestClient


def test_registration_stores_a_lowercase_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register/candidate",
        json={
            "email": "Priya@Example.COM",
            "password": "correct-horse-battery",
            "full_name": "Priya",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "priya@example.com"


def test_candidate_can_view_own_profile(client: TestClient, candidate: dict) -> None:
    response = client.get(f"/candidates/{candidate['candidate_id']}", headers=candidate["headers"])

    assert response.status_code == 200


def test_other_candidate_cannot_view_a_profile(
    client: TestClient, candidate: dict, make_candidate: Callable
) -> None:
    other = make_candidate("other")

    response = client.get(f"/candidates/{candidate['candidate_id']}", headers=other["headers"])

    assert response.status_code == 404


def test_recruiter_cannot_view_candidate_who_never_applied(
    client: TestClient, candidate: dict, recruiter: dict
) -> None:
    response = client.get(f"/candidates/{candidate['candidate_id']}", headers=recruiter["headers"])

    assert response.status_code == 404


def test_recruiter_can_view_candidate_who_applied_to_their_company(
    client: TestClient, candidate: dict, recruiter: dict, application: dict
) -> None:
    response = client.get(f"/candidates/{candidate['candidate_id']}", headers=recruiter["headers"])

    assert response.status_code == 200


def test_viewing_profiles_requires_login(client: TestClient, candidate: dict) -> None:
    assert client.get(f"/candidates/{candidate['candidate_id']}").status_code == 401


def test_add_resume_returns_201(resume: dict, candidate: dict) -> None:
    assert resume["candidate_id"] == candidate["candidate_id"]


def test_same_resume_file_twice_returns_409(
    client: TestClient, candidate: dict, resume: dict
) -> None:
    response = client.post(
        "/me/resumes",
        json={"name": "Copy", "file_key": "resumes/copy.pdf", "file_hash": "a" * 64},
        headers=candidate["headers"],
    )

    assert response.status_code == 409


def test_list_my_resumes_newest_first(
    client: TestClient, candidate: dict, resume: dict, make_resume: Callable
) -> None:
    newer = make_resume(candidate, name="v2", file_hash="b" * 64)

    names = [r["name"] for r in client.get("/me/resumes", headers=candidate["headers"]).json()]

    assert names == [newer["name"], resume["name"]]


def test_recruiter_cannot_use_candidate_resume_endpoints(
    client: TestClient, recruiter: dict
) -> None:
    response = client.post(
        "/me/resumes",
        json={"name": "CV", "file_key": "resumes/r.pdf", "file_hash": "a" * 64},
        headers=recruiter["headers"],
    )

    assert response.status_code == 403
