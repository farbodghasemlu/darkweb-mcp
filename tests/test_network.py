import asyncio
import gzip
import socket
import pytest
from onion_search_mcp.errors import OnionError
from onion_search_mcp.network import BoundedDecoder
from conftest import A, B, C
async def test_socks_remote_dns_headers_and_stream_isolation(transport, socks, monkeypatch):
    def no_dns(*args, **kwargs):
        raise AssertionError("Local DNS was used")
    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    monkeypatch.setenv("HTTP_PROXY", "http://example.com:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://example.com:9999")
    monkeypatch.setenv("ALL_PROXY", "http://example.com:9999")
    await transport.fetch(A)
    await transport.fetch(A + "/page")
    await transport.fetch(C)
    assert all(x[0].endswith(".onion") for x in socks.targets)
    assert socks.credentials[0] == socks.credentials[1] and socks.credentials[0] != socks.credentials[2]
    assert all(x["method"] == "GET" for x in socks.requests)
    assert all("Referer" not in x["headers"] and "Cookie" not in x["headers"] for x in socks.requests)
async def test_redirect_cannot_escape_tor(transport, socks):
    socks.routes["/"] = (302, {"Location": "https://example.com"}, b"")
    with pytest.raises(OnionError, match="INVALID_ONION"):
        await transport.fetch(A)
    assert len(socks.requests) == 1
async def test_redirects_check_blocklist_and_switch(transport, socks):
    socks.routes["/"] = (302, {"Location": B + "/destination"}, b"")
    with pytest.raises(OnionError, match="BLOCKED"):
        await transport.fetch(A)
    assert len(socks.requests) == 1
    response = await transport.fetch(A, content_filter=False)
    assert response.url == B + "/destination"
async def test_cookies_are_not_replayed(transport, socks):
    socks.routes["/"] = (200, {"Content-Type": "text/plain", "Set-Cookie": "identity=secret"}, b"hello")
    await transport.fetch(A)
    await transport.fetch(A + "/next")
    assert "Cookie" not in socks.requests[-1]["headers"]
async def test_media_metadata_without_reading_body(transport, socks):
    socks.routes["/image"] = (200, {"Content-Type": "image/png", "Content-Length": "999999999"}, b"")
    result = await transport.fetch(A + "/image")
    assert result.bytes == 0 and result.body == "" and not result.supported and result.content_length == 999999999
async def test_total_timeout_on_slow_response(transport, socks):
    async def slow(writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100\r\n\r\nx")
        await writer.drain()
        await asyncio.sleep(5)
    socks.routes["/slow"] = slow
    with pytest.raises(OnionError, match="TIMEOUT"):
        await transport.fetch(A + "/slow", timeout_s=0.05)
async def test_compressed_response_cap_and_valid_gzip(transport, socks, settings):
    settings.max_fetch_bytes = 1024
    socks.routes["/bomb"] = (200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"}, gzip.compress(b"x" * 500000))
    with pytest.raises(OnionError, match="RESPONSE_TOO_LARGE"):
        await transport.fetch(A + "/bomb")
    socks.routes["/gzip"] = (200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"}, gzip.compress(b"hello"))
    assert (await transport.fetch(A + "/gzip")).body == "hello"
def test_concatenated_and_truncated_gzip():
    decoder = BoundedDecoder("gzip", 100)
    data = gzip.compress(b"hello") + gzip.compress(b" world")
    result = b"".join(decoder.feed(data[i:i + 3]) for i in range(0, len(data), 3))
    decoder.finish()
    assert result == b"hello world"
    decoder = BoundedDecoder("gzip", 100)
    decoder.feed(gzip.compress(b"hello")[:-4])
    with pytest.raises(OnionError, match="UNSUPPORTED_CONTENT"):
        decoder.finish()
