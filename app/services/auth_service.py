import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import Candidate, Company, RefreshToken, User
from app.models.enums import UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CandidateRegister, CompanyRegister, Token

ACCOUNT_EXISTS = "An account with this email or company slug already exists"
INVALID_REFRESH = "Invalid or expired refresh token"


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.companies = CompanyRepository(db)
        self.candidates = CandidateRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.audit = AuditRepository(db)

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

    def login(self, email: str, password: str) -> Token:
        user = self.authenticate(email, password)
        tokens = self._issue_tokens(user, family_id=uuid.uuid4())  # new device, new family
        self.audit.record(
            actor_user_id=user.id, action="auth.login", entity_type="user", entity_id=user.id
        )
        self.db.commit()
        return tokens

    def refresh(self, raw_token: str) -> Token:
        # Lock the row: if the same token arrives twice at once, the second
        # request waits, then sees it already used and is treated as reuse.
        token = self.refresh_tokens.get_by_hash(hash_refresh_token(raw_token), for_update=True)
        if token is None:
            raise UnauthorizedError(INVALID_REFRESH)

        if token.revoked_at is not None:
            # A used token came back: either an attacker or the real user holds
            # a stolen copy, and we can't tell which. End the whole session.
            self.refresh_tokens.revoke_family(token.family_id)
            self.audit.record(
                actor_user_id=token.user_id,
                action="auth.refresh_token_reused",
                entity_type="user",
                entity_id=token.user_id,
                details={"family_id": str(token.family_id)},
            )
            self.db.commit()  # commit BEFORE raising, or the revocation is rolled back
            raise UnauthorizedError(INVALID_REFRESH)

        user = self.users.get(token.user_id)
        if token.expires_at <= datetime.now(UTC) or user is None or not user.is_active:
            self.db.commit()  # release the row lock
            raise UnauthorizedError(INVALID_REFRESH)

        token.revoked_at = datetime.now(UTC)  # rotation: each refresh token works once
        tokens = self._issue_tokens(user, family_id=token.family_id)
        self.db.commit()
        return tokens

    def logout(self, raw_token: str) -> None:
        token = self.refresh_tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is None:
            return  # nothing to do, and don't reveal whether the token existed
        revoked = self.refresh_tokens.revoke_family(token.family_id)
        if revoked:
            self.audit.record(
                actor_user_id=token.user_id,
                action="auth.logout",
                entity_type="user",
                entity_id=token.user_id,
            )
        self.db.commit()

    def logout_all(self, user: User) -> int:
        revoked = self.refresh_tokens.revoke_all_for_user(user.id)
        self.audit.record(
            actor_user_id=user.id,
            action="auth.logout_all",
            entity_type="user",
            entity_id=user.id,
            details={"revoked_tokens": revoked},
        )
        self.db.commit()
        return revoked

    def _issue_tokens(self, user: User, *, family_id: uuid.UUID) -> Token:
        raw_refresh = generate_refresh_token()
        self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_refresh),
                family_id=family_id,
                expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
            )
        )
        return Token(
            access_token=create_access_token(user.id, user.role),
            refresh_token=raw_refresh,
        )
