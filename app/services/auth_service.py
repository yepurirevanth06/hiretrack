from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models import Candidate, Company, User
from app.models.enums import UserRole
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CandidateRegister, CompanyRegister

ACCOUNT_EXISTS = "An account with this email or company slug already exists"


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.companies = CompanyRepository(db)
        self.candidates = CandidateRepository(db)

    def register_candidate(self, data: CandidateRegister) -> User:
        email = data.email.lower()
        if self.users.get_by_email(email) is not None:
            raise ConflictError(ACCOUNT_EXISTS)

        try:
            candidate = Candidate(email=email, full_name=data.full_name, phone=data.phone)
            self.candidates.add(candidate)
            user = User(
                email=email,
                password_hash=hash_password(data.password),
                role=UserRole.CANDIDATE,
                candidate_id=candidate.id,
            )
            self.users.add(user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(ACCOUNT_EXISTS) from exc

        self.db.refresh(user)
        return user

    def register_company(self, data: CompanyRegister) -> User:
        email = data.email.lower()
        if self.users.get_by_email(email) is not None:
            raise ConflictError(ACCOUNT_EXISTS)

        try:
            company = Company(name=data.company_name, slug=data.company_slug)
            self.companies.add(company)
            user = User(
                email=email,
                password_hash=hash_password(data.password),
                role=UserRole.RECRUITER,
                company_id=company.id,
            )
            self.users.add(user)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(ACCOUNT_EXISTS) from exc

        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email.lower())
        password_ok = verify_password(password, user.password_hash if user else None)
        if user is None or not password_ok or not user.is_active:
            raise UnauthorizedError("Incorrect email or password")
        return user
