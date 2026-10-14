from datetime import datetime, timezone
from pydantic import BaseModel, Field
def now() -> str:
    return datetime.now(timezone.utc).isoformat()
class Source(BaseModel):
    engine: str | None = None
    url: str | None = None
    fetched_at: str = Field(default_factory=now)
    tor_circuit_id: str | None = None
class RawResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    rank: int = Field(ge=1)
    source: Source
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    engines: list[str]
    score: int
    first_seen: str
    source: list[Source]
    verified: bool = False
class Page(BaseModel):
    url: str
    status: int
    content_type: str
    bytes: int
    content_length: int | None = None
    body: str = ""
    source: Source
    supported: bool = True
