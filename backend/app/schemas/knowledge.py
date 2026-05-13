from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeLookupRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=400, description="Natural-language question about FIA regulations")
    k: int = Field(3, ge=1, le=10, description="Maximum number of citations to return")


class KnowledgeCitation(BaseModel):
    id: str
    title: str
    source: str
    section: str
    topics: list[str] = Field(default_factory=list)
    snippet: str
    score: float


class KnowledgeLookupResponse(BaseModel):
    status: Literal["success", "error"]
    query: str
    citations: list[KnowledgeCitation] = Field(default_factory=list)
    error: str | None = None
