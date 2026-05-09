from typing import List, Optional
from pydantic import BaseModel

class EventInfo(BaseModel):
    name: str
    location: str
    round: int
    official_name: str

class ScheduleResponse(BaseModel):
    year: int
    events: List[EventInfo]
    status: str
    error: Optional[str] = None


class RosterResponse(BaseModel):
    year: int
    event: str
    drivers: List[str]
    source_session: Optional[str] = None
    status: str
    fallback: bool = False
    fallback_reason: Optional[str] = None
    error: Optional[str] = None
