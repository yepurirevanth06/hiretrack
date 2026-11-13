from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    file_key: str = Field(min_length=1, max_length=500)
    file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    name: str
    file_key: str
    file_hash: str
    created_at: datetime
