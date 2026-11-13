from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_candidate_applications_use_a_constant_number_of_queries(
    client: TestClient,
    db: Session,
    company: dict[str, Any],
    candidate: dict[str, Any],
    resume: dict[str, Any],
    query_counter: dict[str, int],
) -> None:
    for i in range(5):
        job = client.post(
            f"/companies/{company['id']}/jobs",
            json={
                "title": f"Job {i}",
                "description": "Test",
                "location": "Remote",
                "employment_type": "full_time",
                "status": "open",
            },
        ).json()
        client.post(
            f"/jobs/{job['id']}/applications",
            json={"candidate_id": candidate["id"], "resume_id": resume["id"]},
        )

    db.expunge_all()  # forget cached objects, like a brand-new request
    query_counter["selects"] = 0

    response = client.get(f"/candidates/{candidate['id']}/applications")

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert query_counter["selects"] <= 2
