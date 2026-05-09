from typing import Literal

from pydantic import BaseModel, Field


RadioClassification = Literal[
    "tyre_issue",
    "brake_issue",
    "engine_issue",
    "traffic",
    "weather",
    "strategy_request",
    "none",
]
RadioSeverity = Literal["low", "medium", "high"]


class RadioRequest(BaseModel):
    transcript: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Team-radio transcript text to classify.",
    )
    driver: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Optional 3-letter driver code the transcript belongs to.",
    )


class RadioResponse(BaseModel):
    status: Literal["success", "error"]
    classification: RadioClassification
    severity: RadioSeverity
    trigger_phrase: str = Field(
        ...,
        description="Verbatim snippet from the transcript that triggered the classification. Empty when classification is 'none'.",
    )
    fallback: bool = False
    fallback_reason: str | None = None
