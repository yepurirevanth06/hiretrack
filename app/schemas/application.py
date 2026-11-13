from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    candidate_id: int
    resume_id: int


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    resume_id: int
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company_id: int


class ResumeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ApplicationDetail(ApplicationRead):
    job: JobSummary
    resume: ResumeSummary
