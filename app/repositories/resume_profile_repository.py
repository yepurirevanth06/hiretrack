from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ResumeProfile


class ResumeProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_resume(self, resume_id: int) -> ResumeProfile | None:
        return self.db.scalar(
            select(ResumeProfile).where(ResumeProfile.resume_id == resume_id)
        )

    def find_cached(
        self, text_hash: str, model: str, prompt_version: str
    ) -> ResumeProfile | None:
        return self.db.scalar(
            select(ResumeProfile)
            .where(
                ResumeProfile.text_hash == text_hash,
                ResumeProfile.model == model,
                ResumeProfile.prompt_version == prompt_version,
            )
            .limit(1)
        )

    def add(self, profile: ResumeProfile) -> ResumeProfile:
        self.db.add(profile)
        self.db.flush()
        return profile
