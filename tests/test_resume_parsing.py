from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.fake import FakeLLM
from app.ai.llm import LLMResult, get_llm
from app.ai.resume_parser import ParsedResume, normalize
from app.core.exceptions import AIUnavailableError
from app.main import app
from app.models import AuditEvent, ResumeProfile

RESUME_TEXT = (
    "Jane Doe, Backend Engineer\n"
    "5 years of experience building APIs with Python, FastAPI and PostgreSQL.\n"
    "Deployed services with Docker on AWS.\n"
)


def make_pdf(lines: list[str]) -> bytes:
    """A tiny but valid one-page PDF, so the tests don't need a PDF library."""
    text = " ".join(f"({line}) '" for line in lines)
    stream = f"BT /F1 11 Tf 72 720 Td 14 TL {text} ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode()


@pytest.fixture
def llm() -> Iterator[FakeLLM]:
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm, None)


def upload(
    client: TestClient,
    user: dict,
    resume_id: int,
    content: bytes = RESUME_TEXT.encode(),
    content_type: str = "text/plain",
):
    return client.post(
        f"/me/resumes/{resume_id}/parse",
        files={"file": ("resume", content, content_type)},
        headers=user["headers"],
    )


def test_parsing_returns_structured_data(
    client: TestClient, llm: FakeLLM, candidate: dict, resume: dict
) -> None:
    response = upload(client, candidate, resume["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["skills"] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Docker",
        "AWS",
    ]
    assert body["data"]["total_years_experience"] == 5.0
    assert body["cached"] is False
    assert body["model"] == "fake-llm"


def test_a_pdf_resume_is_read(
    client: TestClient, llm: FakeLLM, candidate: dict, resume: dict
) -> None:
    pdf = make_pdf(
        ["Jane Doe", "3 years with Java and Spring Boot", "Also Kafka and Redis"]
    )

    response = upload(client, candidate, resume["id"], pdf, "application/pdf")

    assert response.status_code == 200, response.text
    assert set(response.json()["data"]["skills"]) == {
        "Java",
        "Spring Boot",
        "Kafka",
        "Redis",
    }


def test_the_profile_can_be_fetched_after_parsing(
    client: TestClient, llm: FakeLLM, candidate: dict, resume: dict
) -> None:
    url = f"/me/resumes/{resume['id']}/profile"
    assert client.get(url, headers=candidate["headers"]).status_code == 404

    upload(client, candidate, resume["id"])

    response = client.get(url, headers=candidate["headers"])
    assert response.status_code == 200
    assert "Python" in response.json()["data"]["skills"]


def test_identical_text_is_never_sent_to_the_llm_twice(
    client: TestClient,
    llm: FakeLLM,
    candidate: dict,
    make_resume: Callable,
    resume: dict,
) -> None:
    second_resume = make_resume(candidate, name="Copy", file_hash="b" * 64)

    first = upload(client, candidate, resume["id"]).json()
    again = upload(client, candidate, resume["id"]).json()
    other = upload(client, candidate, second_resume["id"]).json()

    assert llm.calls == 1
    assert again["cached"] is True
    assert other["cached"] is True
    assert other["data"] == first["data"]
    assert other["input_tokens"] == 0  # cache hits cost nothing


def test_reparsing_replaces_the_previous_profile(
    client: TestClient, db: Session, llm: FakeLLM, candidate: dict, resume: dict
) -> None:
    upload(client, candidate, resume["id"])
    upload(
        client,
        candidate,
        resume["id"],
        b"Now 9 years of Kubernetes and Terraform work. " * 3,
    )

    profiles = db.scalars(
        select(ResumeProfile).where(ResumeProfile.resume_id == resume["id"])
    ).all()
    assert len(profiles) == 1
    assert profiles[0].data["skills"] == ["Kubernetes", "Terraform"]


def test_parsing_is_recorded_in_the_audit_log(
    client: TestClient, db: Session, llm: FakeLLM, candidate: dict, resume: dict
) -> None:
    upload(client, candidate, resume["id"])

    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "resume.parsed"))
    assert event is not None
    assert event.actor_user_id == candidate["id"]
    assert event.details["cached"] is False
    assert event.details["input_tokens"] > 0


def test_no_database_transaction_is_open_during_the_llm_call(
    client: TestClient, db: Session, candidate: dict, resume: dict
) -> None:
    seen: list[bool] = []

    class SpyLLM(FakeLLM):
        def extract(self, **kwargs: Any) -> LLMResult:  # type: ignore[override]
            seen.append(db.in_transaction())
            return super().extract(**kwargs)

    app.dependency_overrides[get_llm] = SpyLLM
    try:
        assert upload(client, candidate, resume["id"]).status_code == 200
    finally:
        app.dependency_overrides.pop(get_llm, None)

    assert seen == [False]


def test_someone_elses_resume_returns_404(
    client: TestClient, llm: FakeLLM, make_candidate: Callable, resume: dict
) -> None:
    stranger = make_candidate("stranger")

    assert upload(client, stranger, resume["id"]).status_code == 404
    assert llm.calls == 0


def test_recruiters_cannot_use_the_candidate_endpoint(
    client: TestClient, llm: FakeLLM, recruiter: dict, resume: dict
) -> None:
    assert upload(client, recruiter, resume["id"]).status_code == 403


@pytest.mark.parametrize(
    ("content", "content_type", "status"),
    [
        (b"short", "text/plain", 422),  # no real text
        (b"%PDF-1.4 this is not really a pdf", "application/pdf", 422),
        (b"\x89PNG not a resume" * 10, "image/png", 422),
        (b"x" * (2 * 1024 * 1024 + 1), "text/plain", 413),
    ],
)
def test_bad_files_are_rejected_before_calling_the_llm(
    client: TestClient,
    llm: FakeLLM,
    candidate: dict,
    resume: dict,
    content: bytes,
    content_type: str,
    status: int,
) -> None:
    response = upload(client, candidate, resume["id"], content, content_type)

    assert response.status_code == status
    assert llm.calls == 0


def test_an_ai_outage_returns_503_and_saves_nothing(
    client: TestClient, db: Session, candidate: dict, resume: dict
) -> None:
    class DownLLM(FakeLLM):
        def extract(self, **kwargs: Any) -> LLMResult:  # type: ignore[override]
            raise AIUnavailableError("AI provider is unreachable")

    app.dependency_overrides[get_llm] = DownLLM
    try:
        response = upload(client, candidate, resume["id"])
    finally:
        app.dependency_overrides.pop(get_llm, None)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_unavailable"
    assert db.scalar(select(ResumeProfile)) is None


def test_model_output_is_cleaned_before_it_is_stored() -> None:
    messy = ParsedResume(
        summary="  Backend engineer  ",
        skills=["Python", " python ", "", "Fast  API", "x" * 80],
        total_years_experience=-3,
        experience=[],
        education=[],
    )

    clean = normalize(messy)

    assert clean.skills == ["Python", "Fast API"]
    assert clean.total_years_experience == 0
    assert clean.summary == "Backend engineer"
