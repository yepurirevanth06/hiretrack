from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    created_at: datetime
