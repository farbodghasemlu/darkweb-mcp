import asyncio
import random
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode
import yaml
from pydantic import BaseModel, Field, field_validator
from .engine_parsers import PARSERS
from .errors import OnionError
from .models import RawResult, SearchResult
from .urls import normalized_url, onion_url
class EngineConfig(BaseModel):
    url: str
    search_path: str = "/search"
    query_param: str = "q"
    page_param: str = "page"
    extra_params: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    published_address: str | None = None
    verification: str = "needs-operator-verification"
    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        return onion_url(value)
    @field_validator("search_path")
    @classmethod
    def validate_path(cls, value):
        if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value:
            raise ValueError("Search paths must be absolute local paths")
        return value
class SearchEngine(Protocol):
    id: str
    async def search(self, q: str, page: int, content_filter: bool | None = None) -> list[RawResult]: ...
    async def healthy(self) -> bool: ...
class ResultBatch(list):
    def __init__(self, rows, source):
        super().__init__(rows)
        self.source = source
class Adapter:
    def __init__(self, engine_id, config, transport, parser, settings):
        self.id, self.config, self.transport, self.parser, self.settings = engine_id, config, transport, parser, settings
        self.lock, self.next_request, self.last_health, self.last_source = asyncio.Lock(), 0, None, None
    async def search(self, q: str, page: int, content_filter: bool | None = None):
        async with self.lock:
            await asyncio.sleep(max(0, self.next_request - time.monotonic()) + random.uniform(0, self.settings.jitter_s))
            self.next_request = time.monotonic() + self.settings.engine_rate_limit_s
            params = {**self.config.extra_params, self.config.query_param: q, self.config.page_param: str(page)}
            url = f"{self.config.url}{self.config.search_path}?{urlencode(params)}"
            response = await self.transport.fetch(url, content_filter=content_filter, engine=self.id)
            self.last_source = response.source
            if response.status >= 400 or not response.supported:
                raise OnionError("ENGINE_UNAVAILABLE", "The engine returned an unsupported or unsuccessful response.")
            parsed = await self.parser.run("engine", response.body, response.url, engine=self.id)
            self.last_health = True
            return ResultBatch([RawResult(**x, source=response.source) for x in parsed], response.source)
    async def healthy(self):
        try:
            response = await self.transport.fetch(self.config.url, timeout_s=10, metadata=True, engine=self.id)
            self.last_health = response.status < 400
        except OnionError:
            self.last_health = False
        return self.last_health
def load_engines(settings, transport, parser):
    try:
        data = yaml.safe_load(Path(settings.engines_file).read_text())["engines"]
        selected = set(data) if settings.engines == "all" else {x.strip() for x in settings.engines.split(",")}
        if not selected or selected - set(PARSERS) or selected - set(data) or set(data) - set(PARSERS):
            raise ValueError
        engines = {key: Adapter(key, EngineConfig.model_validate(value), transport, parser, settings) for key, value in data.items() if key in selected and value.get("enabled", True)}
        if not engines:
            raise ValueError
        return engines
    except Exception:
        raise OnionError("CONFIG_ERROR", "Engine configuration is invalid or no engines are enabled.") from None
def merge(groups: dict[str, list[RawResult]], filtering, content_filter: bool | None):
    merged = {}
    for engine, rows in groups.items():
        for row in rows:
            try:
                url = normalized_url(row.url)
            except OnionError:
                continue
            if not filtering.allowed(url, row.title + " " + row.snippet, content_filter):
                continue
            bonus = max(0, 21 - row.rank)
            title, snippet = filtering.redact(row.title, content_filter), filtering.redact(row.snippet, content_filter)
            if url not in merged:
                merged[url] = SearchResult(title=title, url=url, snippet=snippet, engines=[], score=0, first_seen=row.source.fetched_at, source=[])
            item = merged[url]
            previous_bonus = item.score - len(item.engines) * 10
            if engine not in item.engines:
                item.engines.append(engine)
                item.source.append(row.source)
            item.title, item.snippet = max((item.title, title), key=len), max((item.snippet, snippet), key=len)
            item.score = len(item.engines) * 10 + max(previous_bonus, bonus)
    return sorted(merged.values(), key=lambda x: (-x.score, x.url))
