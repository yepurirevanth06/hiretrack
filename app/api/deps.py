from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole

DbSession = Annotated[Session, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
TokenDep = Annotated[str | None, Depends(oauth2_scheme)]


def _user_from_token(db: Session, token: str) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token")
    return user


def get_current_user(db: DbSession, token: TokenDep) -> User:
    if token is None:
        raise UnauthorizedError("Not authenticated")
    return _user_from_token(db, token)


def get_optional_user(db: DbSession, token: TokenDep) -> User | None:
    return None if token is None else _user_from_token(db, token)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_recruiter(user: CurrentUser) -> User:
    if user.role != UserRole.RECRUITER:
        raise ForbiddenError("This action requires a recruiter account")
    return user


def get_current_candidate(user: CurrentUser) -> User:
    if user.role != UserRole.CANDIDATE:
        raise ForbiddenError("This action requires a candidate account")
    return user


CurrentRecruiter = Annotated[User, Depends(get_current_recruiter)]
CurrentCandidate = Annotated[User, Depends(get_current_candidate)]
