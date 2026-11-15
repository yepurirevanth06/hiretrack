from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_my_applications_use_a_constant_number_of_queries(
    client: TestClient,
    db: Session,
    recruiter: dict,
    candidate: dict,
    resume: dict,
    make_job: Callable,
    make_application: Callable,
    query_counter: dict[str, int],
) -> None:
    for i in range(5):
        job = make_job(recruiter, title=f"Job {i}")
        make_application(candidate, job, resume)

    db.expunge_all()  # forget cached objects, like a brand-new request
    query_counter["selects"] = 0

    response = client.get("/me/applications", headers=candidate["headers"])

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert query_counter["selects"] <= 2  # load the user from the token + one joined query
