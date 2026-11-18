"""A stand-in for the real LLM: no network, no cost, same answer every time.

Used by the tests, and for local development with LLM_PROVIDER=fake.
"""

import re

from pydantic import BaseModel

from app.ai.llm import LLMResult
from app.ai.resume_parser import ParsedResume

KNOWN_SKILLS = [
    "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "Redis", "Docker",
    "Kubernetes", "AWS", "Java", "Spring Boot", "React", "TypeScript", "SQL",
    "Kafka", "Terraform", "GitHub Actions", "pytest",
]  # fmt: skip


class FakeLLM:
    model = "fake-llm"

    def __init__(self) -> None:
        self.calls = 0

    def extract[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], max_tokens: int = 2048
    ) -> LLMResult[T]:
        self.calls += 1
        if schema is not ParsedResume:
            raise NotImplementedError(f"FakeLLM can't produce {schema.__name__} yet")

        skills = [
            s
            for s in KNOWN_SKILLS
            if re.search(rf"\b{re.escape(s)}\b", user, re.IGNORECASE)
        ]
        years = re.search(r"(\d+(?:\.\d+)?)\+?\s+years", user, re.IGNORECASE)
        output = ParsedResume(
            summary="Parsed by FakeLLM",
            skills=skills,
            total_years_experience=float(years.group(1)) if years else 0.0,
            experience=[],
            education=[],
        )
        return LLMResult(
            output=output,  # type: ignore[arg-type]
            model=self.model,
            input_tokens=len(user) // 4,
            output_tokens=50,
            latency_ms=1,
        )
