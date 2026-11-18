from typing import Any

from sqlalchemy.orm import Session

from app.ai.llm import LLMClient
from app.ai.resume_parser import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    ParsedResume,
    build_user_message,
    extract_text,
    normalize,
    text_hash,
)
from app.core.exceptions import NotFoundError
from app.models import Resume, ResumeProfile, User
from app.repositories.audit_repository import AuditRepository
from app.repositories.resume_profile_repository import ResumeProfileRepository
from app.repositories.resume_repository import ResumeRepository


class ResumeAIService:
    def __init__(self, db: Session, llm: LLMClient | None = None) -> None:
        self.db = db
        self.llm = llm
        self.resumes = ResumeRepository(db)
        self.profiles = ResumeProfileRepository(db)
        self.audit = AuditRepository(db)

    def parse(
        self, resume_id: int, user: User, file: bytes, content_type: str | None
    ) -> tuple[ResumeProfile, bool]:
        """Returns the stored profile and whether it came from the cache."""
        self._own_resume(resume_id, user)
        text = extract_text(file, content_type)
        digest = text_hash(text)
        model = getattr(self.llm, "model", "unknown")

        cached = self.profiles.find_cached(digest, model, PROMPT_VERSION)
        if cached is not None:
            # Same text, same model, same prompt: the answer would be the same,
            # so reuse it instead of paying for another call.
            values: dict[str, Any] = {
                "data": cached.data,
                "model": cached.model,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
            }
            return self._save(resume_id, user, digest, values, from_cache=True), True

        # An LLM call can take seconds. End the transaction first, so we don't
        # hold a database connection (and any row locks) while we wait.
        self.db.commit()

        assert self.llm is not None
        result = self.llm.extract(
            system=SYSTEM_PROMPT, user=build_user_message(text), schema=ParsedResume
        )
        values = {
            "data": normalize(result.output).model_dump(),
            "model": model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        }
        return self._save(resume_id, user, digest, values, from_cache=False), False

    def get_profile(self, resume_id: int, user: User) -> ResumeProfile:
        self._own_resume(resume_id, user)
        profile = self.profiles.get_for_resume(resume_id)
        if profile is None:
            raise NotFoundError(f"Resume {resume_id} hasn't been parsed yet")
        return profile

    def _own_resume(self, resume_id: int, user: User) -> Resume:
        resume = self.resumes.get(resume_id)
        if (
            resume is None
            or resume.candidate_id != user.candidate_id
            or resume.deleted_at
        ):
            raise NotFoundError(f"Resume {resume_id} not found")
        return resume

    def _save(
        self,
        resume_id: int,
        user: User,
        digest: str,
        values: dict[str, Any],
        *,
        from_cache: bool,
    ) -> ResumeProfile:
        profile = self.profiles.get_for_resume(resume_id)
        if profile is None:
            profile = self.profiles.add(
                ResumeProfile(
                    resume_id=resume_id,
                    text_hash=digest,
                    prompt_version=PROMPT_VERSION,
                    **values,
                )
            )
        else:  # re-parsing replaces the previous result
            profile.text_hash = digest
            profile.prompt_version = PROMPT_VERSION
            for key, value in values.items():
                setattr(profile, key, value)

        self.audit.record(
            actor_user_id=user.id,
            action="resume.parsed",
            entity_type="resume",
            entity_id=resume_id,
            details={
                "model": values["model"],
                "cached": from_cache,
                "input_tokens": values["input_tokens"],
                "output_tokens": values["output_tokens"],
                "latency_ms": values["latency_ms"],
            },
        )
        self.db.commit()
        self.db.refresh(profile)
        return profile
