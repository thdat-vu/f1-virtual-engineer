from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeHistoryItem(BaseModel):
    id: UUID
    query: str
    driver: str | None = None
    event: str | None = None
    year: int | None = None
    session_type: str | None = None
    intent_type: str | None = None
    rationale_source: str
    created_at: datetime


class AnalyzeHistoryResponse(BaseModel):
    items: list[AnalyzeHistoryItem] = Field(default_factory=list)
