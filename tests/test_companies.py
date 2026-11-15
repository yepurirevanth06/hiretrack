import pytest
from fastapi.testclient import TestClient

PASSWORD = "correct-horse-battery"


def register_company(client: TestClient, slug: str, email: str):
    return client.post(
        "/auth/register/company",
        json={"company_name": "Acme", "company_slug": slug, "email": email, "password": PASSWORD},
    )


def test_company_profile_is_public(client: TestClient, recruiter: dict) -> None:
    response = client.get(f"/companies/{recruiter['company_id']}")

    assert response.status_code == 200
    assert response.json()["slug"] == "acme-corp"


def test_missing_company_returns_404(client: TestClient) -> None:
    assert client.get("/companies/999999").status_code == 404


def test_duplicate_slug_returns_409(client: TestClient, recruiter: dict) -> None:
    # The service only pre-checks the email, so this duplicate is caught by the
    # database's unique constraint on the slug: the race-safe path.
    response = register_company(client, "acme-corp", "someone-else@acme.com")

    assert response.status_code == 409


@pytest.mark.parametrize("slug", ["Acme Corp!", "UPPERCASE", "a", "-starts", "ends-", "double--dash"])
def test_invalid_slug_returns_422(client: TestClient, slug: str) -> None:
    assert register_company(client, slug, "a@example.com").status_code == 422
