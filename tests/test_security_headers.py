from fastapi.testclient import TestClient


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "max-age=" in response.headers["strict-transport-security"]
    assert response.headers["content-security-policy"].startswith("default-src 'none'")


def test_error_responses_carry_them_too(client: TestClient) -> None:
    response = client.get("/jobs/999999999")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"


def test_swagger_ui_still_loads(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers


def test_cors_allows_the_configured_frontend(client: TestClient) -> None:
    response = client.options(
        "/jobs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_ignores_unknown_origins(client: TestClient) -> None:
    response = client.options(
        "/jobs",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
