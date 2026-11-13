from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Resume


class ResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, resume_id: int) -> Resume | None:
        return self.db.get(Resume, resume_id)

    def get_by_hash(self, candidate_id: int, file_hash: str) -> Resume | None:
        return self.db.scalar(
            select(Resume).where(
                Resume.candidate_id == candidate_id, Resume.file_hash == file_hash
            )
        )

    def list_active(self, candidate_id: int) -> list[Resume]:
        query = (
            select(Resume)
            .where(Resume.candidate_id == candidate_id, Resume.deleted_at.is_(None))
            .order_by(Resume.created_at.desc(), Resume.id.desc())
        )
        return list(self.db.scalars(query).all())

    def add(self, resume: Resume) -> Resume:
        self.db.add(resume)
        self.db.flush()
        return resume
