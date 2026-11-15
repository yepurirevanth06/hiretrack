from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.models import User
from app.schemas.auth import CandidateRegister, CompanyRegister, Token, UserRead
from app.schemas.error import ErrorResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

CONFLICT = {409: {"model": ErrorResponse, "description": "Email or company slug already used"}}
UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Not authenticated"}}


@router.post(
    "/register/candidate",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
)
def register_candidate(data: CandidateRegister, db: DbSession) -> User:
    return AuthService(db).register_candidate(data)


@router.post(
    "/register/company",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
)
def register_company(data: CompanyRegister, db: DbSession) -> User:
    return AuthService(db).register_company(data)


@router.post("/token", response_model=Token, responses=UNAUTHORIZED)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> Token:
    user = AuthService(db).authenticate(form.username, form.password)
    return Token(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserRead, responses=UNAUTHORIZED)
def me(user: CurrentUser) -> User:
    return user
