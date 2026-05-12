from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


SavedQueryKind = Literal["analyze", "telemetry"]


class SavedQueryCreateRequest(BaseModel):
    kind: SavedQueryKind
    payload: dict[str, Any]
    label: str | None = Field(default=None, max_length=120)


class SavedQueryItem(BaseModel):
    id: UUID
    kind: SavedQueryKind
    payload: dict[str, Any]
    label: str | None = None
    created_at: datetime


class SavedQueryListResponse(BaseModel):
    items: list[SavedQueryItem] = Field(default_factory=list)
