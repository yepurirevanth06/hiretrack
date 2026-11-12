from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company


class CompanyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, company_id: int) -> Company | None:
        return self.db.get(Company, company_id)

    def get_by_slug(self, slug: str) -> Company | None:
        return self.db.scalar(select(Company).where(Company.slug == slug))

    def add(self, company: Company) -> Company:
        self.db.add(company)
        self.db.flush()
        return company
