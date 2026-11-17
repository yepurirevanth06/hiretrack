from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.auth import (
    CandidateRegister,
    CompanyRegister,
    RefreshRequest,
    Token,
    UserRead,
)
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
    return AuthService(db).login(form.username, form.password)


@router.post("/refresh", response_model=Token, responses=UNAUTHORIZED)
def refresh(data: RefreshRequest, db: DbSession) -> Token:
    return AuthService(db).refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, db: DbSession) -> None:
    AuthService(db).logout(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, responses=UNAUTHORIZED)
def logout_all(user: CurrentUser, db: DbSession) -> None:
    AuthService(db).logout_all(user)


@router.get("/me", response_model=UserRead, responses=UNAUTHORIZED)
def me(user: CurrentUser) -> User:
    return user
