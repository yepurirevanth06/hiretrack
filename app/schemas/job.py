from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmploymentType, JobStatus


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    location: str = Field(min_length=1, max_length=200)
    employment_type: EmploymentType
    status: JobStatus = JobStatus.DRAFT


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    description: str
    location: str
    employment_type: EmploymentType
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class JobPage(BaseModel):
    items: list[JobRead]
    next_cursor: str | None
    total: int | None = None


class JobCloseResult(BaseModel):
    job: JobRead
    rejected_applications: int
