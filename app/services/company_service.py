from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Company
from app.repositories.company_repository import CompanyRepository


class CompanyService:
    def __init__(self, db: Session) -> None:
        self.companies = CompanyRepository(db)

    def get(self, company_id: int) -> Company:
        company = self.companies.get(company_id)
        if company is None:
            raise NotFoundError(f"Company {company_id} not found")
        return company
