import socket
import pytest
from onion_search_mcp.config import Settings
from onion_search_mcp.control import TorControl
from onion_search_mcp.errors import OnionError
from onion_search_mcp.network import TorTransport
from onion_search_mcp.safety import ContentFilter
from conftest import A
async def test_stopped_tor_never_connects_to_destination(settings, monkeypatch):
    original = socket.socket.connect
    attempts = []
    reserved = socket.socket()
    reserved.bind(("127.0.0.1", 0))
    port = reserved.getsockname()[1]
    reserved.close()
    settings.tor_socks = f"127.0.0.1:{port}"
    def guard(sock, address):
        attempts.append(address)
        assert address[0] == "127.0.0.1" and address[1] == port
        return original(sock, address)
    def dns(*args, **kwargs):
        raise AssertionError("Destination DNS leaked")
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    transport = TorTransport(settings, ContentFilter(settings), TorControl(settings))
    try:
        with pytest.raises(OnionError, match="TOR_UNAVAILABLE") as error:
            await transport.fetch(A)
        assert attempts and A not in str(error.value)
    finally:
        await transport.close()
@pytest.mark.parametrize("endpoint", ["localhost:9050", "tor:9050", "example.com:9050", "127.0.0.1:0"])
def test_proxy_names_cannot_trigger_local_dns(endpoint):
    with pytest.raises(ValueError):
        Settings(tor_socks=endpoint)
