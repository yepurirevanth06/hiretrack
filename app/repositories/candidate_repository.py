from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate


class CandidateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, candidate_id: int) -> Candidate | None:
        return self.db.get(Candidate, candidate_id)

    def get_by_email(self, email: str) -> Candidate | None:
        return self.db.scalar(select(Candidate).where(Candidate.email == email))

    def add(self, candidate: Candidate) -> Candidate:
        self.db.add(candidate)
        self.db.flush()
        return candidate
