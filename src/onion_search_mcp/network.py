import asyncio
import hashlib
import secrets
import zlib
from http.cookiejar import CookieJar
from urllib.parse import quote, urljoin, urlsplit
import httpx
from httpx_socks import AsyncProxyTransport
from .errors import OnionError
from .models import Page
from .urls import onion_url
TEXT_TYPES = {"application/xhtml+xml", "application/json", "application/xml", "application/rss+xml", "application/atom+xml"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0", "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1", "Accept-Language": "en-US,en;q=0.5", "Accept-Encoding": "identity", "DNT": "1"}
class NoCookies(CookieJar):
    def set_cookie(self, cookie, *args, **kwargs):
        pass
class BoundedDecoder:
    def __init__(self, encoding: str, cap: int):
        self.cap, self.size, self.raw_size, self.encoding = cap, 0, 0, encoding
        if encoding not in {"", "identity", "gzip", "deflate"}:
            raise OnionError("UNSUPPORTED_CONTENT", "Unsupported response encoding.")
        self.decoder = zlib.decompressobj(31 if encoding == "gzip" else 15) if encoding in {"gzip", "deflate"} else None
    def feed(self, data: bytes) -> bytes:
        self.raw_size += len(data)
        if self.raw_size > self.cap:
            raise OnionError("RESPONSE_TOO_LARGE", "The response exceeded the byte limit.")
        out = bytearray()
        try:
            while data:
                if not self.decoder:
                    out.extend(data)
                    break
                if self.decoder.eof:
                    if self.encoding != "gzip":
                        raise zlib.error
                    self.decoder = zlib.decompressobj(31)
                out.extend(self.decoder.decompress(data, self.cap - self.size - len(out) + 1))
                if self.size + len(out) > self.cap:
                    raise OnionError("RESPONSE_TOO_LARGE", "The decompressed response exceeded the byte limit.")
                data = self.decoder.unused_data or self.decoder.unconsumed_tail
        except zlib.error:
            raise OnionError("UNSUPPORTED_CONTENT", "Malformed compressed response.") from None
        self.size += len(out)
        if self.size > self.cap:
            raise OnionError("RESPONSE_TOO_LARGE", "The response exceeded the byte limit.")
        return bytes(out)
    def finish(self):
        if self.decoder and not self.decoder.eof:
            raise OnionError("UNSUPPORTED_CONTENT", "Incomplete compressed response.")
class TorTransport:
    def __init__(self, settings, filtering, control):
        self.settings, self.filtering, self.control = settings, filtering, control
        self.session, self.clients, self.usernames = secrets.token_hex(24), {}, {}
        self.gate = asyncio.Semaphore(8)
    def client(self, host: str):
        if host not in self.clients:
            username = hashlib.sha256(f"{self.session}:{host}".encode()).hexdigest()[:48]
            self.usernames[host] = username
            proxy = f"socks5://{quote(username)}:{self.session}@{self.settings.tor_socks}"
            transport = AsyncProxyTransport.from_url(proxy, rdns=True, retries=0)
            self.clients[host] = httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False, headers=HEADERS, cookies=NoCookies(),
                                                timeout=httpx.Timeout(15, connect=None), limits=httpx.Limits(max_connections=2, max_keepalive_connections=0))
            if len(self.clients) > 128:
                oldest = next(iter(self.clients))
                if oldest != host:
                    client = self.clients.pop(oldest)
                    self.usernames.pop(oldest, None)
                    asyncio.create_task(client.aclose())
        return self.clients[host]
    async def fetch(self, url: str, timeout_s: float | None = None, metadata: bool = False, content_filter: bool | None = None, engine: str | None = None) -> Page:
        url = onion_url(url)
        try:
            async with asyncio.timeout(timeout_s or self.settings.request_timeout_s), self.gate:
                return await self._fetch(url, metadata, content_filter, engine)
        except (TimeoutError, httpx.TimeoutException):
            raise OnionError("TIMEOUT", "The onion service did not respond before the time limit.") from None
        except OnionError:
            raise
        except (httpx.HTTPError, OSError):
            raise OnionError("TOR_UNAVAILABLE", "The Tor connection or onion service is unavailable.") from None
        except Exception:
            raise OnionError("TOR_UNAVAILABLE", "The Tor request failed.") from None
    async def _fetch(self, url: str, metadata: bool, content_filter: bool | None, engine: str | None) -> Page:
        for _ in range(6):
            if self.filtering.blocked(url, content_filter):
                raise OnionError("BLOCKED", "The destination is blocked by the content filter.")
            host = urlsplit(url).netloc
            client = self.client(host)
            client.cookies.clear()
            async with client.stream("GET", url) as response:
                client.cookies.clear()
                if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
                    url = onion_url(urljoin(url, response.headers["location"]))
                    continue
                kind = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                supported = kind.startswith("text/") or kind in TEXT_TYPES
                raw_length = response.headers.get("content-length", "")
                length = int(raw_length) if raw_length.isdigit() else None
                source = self.control.source(url, self.usernames[host], engine)
                page = Page(url=url, status=response.status_code, content_type=kind, bytes=0, content_length=length, source=source, supported=supported)
                if metadata or not supported:
                    return page
                decoder = BoundedDecoder(response.headers.get("content-encoding", "").strip().lower(), self.settings.max_fetch_bytes)
                body = bytearray()
                async for chunk in response.aiter_raw(chunk_size=16384):
                    body.extend(decoder.feed(chunk))
                decoder.finish()
                page.body, page.bytes = bytes(body).decode("utf-8", errors="replace"), len(body)
                page.source = self.control.source(url, self.usernames[host], engine)
                return page
        raise OnionError("REDIRECT_LIMIT", "The response exceeded the redirect limit.")
    async def health(self):
        host, port = self.settings.tor_socks.rsplit(":", 1)
        try:
            async with asyncio.timeout(3):
                reader, writer = await asyncio.open_connection(host.strip("[]"), int(port))
                try:
                    writer.write(b"\x05\x01\x00")
                    await writer.drain()
                    return await reader.readexactly(2) == b"\x05\x00"
                finally:
                    writer.close()
                    await writer.wait_closed()
        except (OSError, TimeoutError, asyncio.IncompleteReadError):
            return False
    async def close(self):
        await asyncio.gather(*(c.aclose() for c in self.clients.values()), return_exceptions=True)
        self.clients.clear()
        self.usernames.clear()
        self.session = ""
