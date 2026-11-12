from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories.company_repository import CompanyRepository


def test_create_company_returns_201(client: TestClient) -> None:
    response = client.post("/companies", json={"name": "Acme Corp", "slug": "acme-corp"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    assert body["slug"] == "acme-corp"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_duplicate_slug_returns_409(client: TestClient, company: dict[str, Any]) -> None:
    response = client.post("/companies", json={"name": "Another", "slug": "acme-corp"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_duplicate_slug_race_is_caught_by_database(
    client: TestClient, company: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a race: the service check sees no duplicate, so only the
    # database unique constraint can stop the second insert.
    monkeypatch.setattr(CompanyRepository, "get_by_slug", lambda self, slug: None)

    response = client.post("/companies", json={"name": "Another", "slug": "acme-corp"})

    assert response.status_code == 409


@pytest.mark.parametrize("slug", ["Acme Corp!", "UPPERCASE", "a", "-starts", "ends-", "double--dash"])
def test_invalid_slug_returns_422(client: TestClient, slug: str) -> None:
    response = client.post("/companies", json={"name": "Acme", "slug": slug})

    assert response.status_code == 422


def test_get_company_returns_200(client: TestClient, company: dict[str, Any]) -> None:
    response = client.get(f"/companies/{company['id']}")

    assert response.status_code == 200
    assert response.json()["slug"] == "acme-corp"


def test_get_missing_company_returns_404(client: TestClient) -> None:
    response = client.get("/companies/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
