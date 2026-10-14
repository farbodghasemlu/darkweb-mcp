from ipaddress import ip_address
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .errors import OnionError
DATA = Path(__file__).parent / "data"
def data_path(local: str, packaged: str) -> str:
    return local if Path(local).is_file() else str(DATA / packaged)
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    tor_socks: str = "127.0.0.1:9050"
    tor_control: str = "127.0.0.1:9051"
    tor_control_password: str | None = None
    tor_cookie_file: str | None = None
    tor_bridges: str = ""
    engines: str = "all"
    engines_file: str = Field(default_factory=lambda: data_path("engines.yaml", "engines.yaml"))
    blocklist_paths: str = Field(default_factory=lambda: data_path("blocklists/csam.txt", "csam.txt"))
    terms_file: str = Field(default_factory=lambda: data_path("blocklists/terms.txt", "terms.txt"))
    keyword_filter: bool = False
    filter_keywords: str = ""
    content_filter: bool = True
    max_fetch_bytes: int = Field(default=5242880, ge=1024, le=5242880)
    cache_ttl_s: int = Field(default=900, ge=0, le=86400)
    fetch_cache_ttl_s: int = Field(default=600, ge=0, le=86400)
    cache_max_entries: int = Field(default=128, ge=1, le=4096)
    cache_max_bytes: int = Field(default=33554432, ge=1024, le=268435456)
    engine_timeout_s: float = Field(default=25, gt=0, le=25)
    search_timeout_s: float = Field(default=40, gt=0, le=40)
    request_timeout_s: float = Field(default=40, gt=0, le=120)
    engine_rate_limit_s: float = Field(default=3, ge=0, le=300)
    jitter_s: float = Field(default=2, ge=0, le=2)
    log_queries: bool = False
    @field_validator("tor_socks", "tor_control")
    @classmethod
    def endpoint(cls, value: str) -> str:
        try:
            host, port = value.rsplit(":", 1)
            ip_address(host.strip("[]"))
            if not 1 <= int(port) <= 65535:
                raise ValueError
            return value
        except ValueError:
            raise ValueError("Tor endpoints must be numeric IP:port addresses; DNS lookup is disabled") from None
    @field_validator("log_queries")
    @classmethod
    def no_logging(cls, value: bool) -> bool:
        if value:
            raise ValueError("Query logging is unavailable; session history is memory only")
        return value
    def checked(self):
        if not Path(self.engines_file).is_file():
            raise OnionError("CONFIG_ERROR", "Engine configuration is missing.")
        return self
