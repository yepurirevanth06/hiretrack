from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.ai.resume_parser import ResumeData


class ResumeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resume_id: int
    data: ResumeData
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cached: bool = False
    updated_at: datetime
