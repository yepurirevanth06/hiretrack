from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyCreate


class CompanyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.companies = CompanyRepository(db)

    def create(self, data: CompanyCreate) -> Company:
        if self.companies.get_by_slug(data.slug) is not None:
            raise ConflictError(f"Company slug '{data.slug}' is already taken")

        company = Company(name=data.name, slug=data.slug)
        try:
            self.companies.add(company)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"Company slug '{data.slug}' is already taken") from exc

        self.db.refresh(company)
        return company

    def get(self, company_id: int) -> Company:
        company = self.companies.get(company_id)
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")
        return company
