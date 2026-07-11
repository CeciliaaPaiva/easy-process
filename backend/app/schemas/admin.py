import uuid
from datetime import datetime

from pydantic import BaseModel


class UsageByStage(BaseModel):
    stage: str
    calls: int
    prompt_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class UsageByDay(BaseModel):
    day: str
    calls: int
    total_tokens: int
    estimated_cost_usd: float


class UsageLogEntry(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    process_id: uuid.UUID | None
    stage: str
    model: str
    attempt: int
    prompt_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float
    by_stage: list[UsageByStage]
    by_day: list[UsageByDay]
    recent_logs: list[UsageLogEntry]
