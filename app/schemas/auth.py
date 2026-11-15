from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class CandidateRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)


class CompanyRegister(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    company_slug: str = Field(
        min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    company_id: int | None
    candidate_id: int | None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
