import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import pytest
from onion_search_mcp.config import Settings
from onion_search_mcp.control import TorControl
from onion_search_mcp.network import TorTransport
from onion_search_mcp.safety import ContentFilter
ROOT = Path(__file__).resolve().parents[1]
A, B, C = (f"http://{x * 56}.onion" for x in "abc")
@pytest.fixture
def settings(tmp_path):
    blocklist = tmp_path / "blocked.txt"
    blocklist.write_text(f"{'b' * 56}.onion\n")
    return Settings(engines_file=str(ROOT / "engines.yaml"), blocklist_paths=str(blocklist), terms_file=str(ROOT / "blocklists/terms.txt"),
                    jitter_s=0, engine_rate_limit_s=0, tor_control="127.0.0.1:1")
@dataclass
class SocksServer:
    port: int = 0
    routes: dict = field(default_factory=dict)
    requests: list = field(default_factory=list)
    credentials: list = field(default_factory=list)
    targets: list = field(default_factory=list)
    tasks: set = field(default_factory=set)
    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            greeting = await reader.readexactly(2)
            methods = await reader.readexactly(greeting[1])
            method = 2 if 2 in methods else 0
            writer.write(bytes((5, method)))
            await writer.drain()
            if method == 2:
                header = await reader.readexactly(2)
                username = await reader.readexactly(header[1])
                password = await reader.readexactly((await reader.readexactly(1))[0])
                self.credentials.append((username.decode(), password.decode()))
                writer.write(b"\x01\x00")
                await writer.drain()
            connect = await reader.readexactly(4)
            assert connect == b"\x05\x01\x00\x03"
            host = (await reader.readexactly((await reader.readexactly(1))[0])).decode()
            port = int.from_bytes(await reader.readexactly(2), "big")
            self.targets.append((host, port))
            writer.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x50")
            await writer.drain()
            raw = await reader.readuntil(b"\r\n\r\n")
            lines = raw.decode().split("\r\n")
            method, path, _ = lines[0].split()
            headers = dict(line.split(": ", 1) for line in lines[1:] if ": " in line)
            self.requests.append({"method": method, "path": path, "headers": headers, "host": host})
            route = self.routes.get(path, (200, {"Content-Type": "text/html"}, b"<html><title>Example</title><body><p>Fixture text.</p></body></html>"))
            if callable(route):
                await route(writer)
            else:
                status, headers, body = route
                header = {"Content-Length": str(len(body)), "Connection": "close", **headers}
                data = f"HTTP/1.1 {status} Test\r\n" + "".join(f"{k}: {v}\r\n" for k, v in header.items()) + "\r\n"
                writer.write(data.encode() + body)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)
@pytest.fixture
async def socks(settings):
    proxy = SocksServer()
    server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
    proxy.port = server.sockets[0].getsockname()[1]
    settings.tor_socks = f"127.0.0.1:{proxy.port}"
    try:
        yield proxy
    finally:
        server.close()
        await server.wait_closed()
        for task in list(proxy.tasks):
            task.cancel()
        await asyncio.gather(*proxy.tasks, return_exceptions=True)
@pytest.fixture
async def transport(settings, socks):
    network = TorTransport(settings, ContentFilter(settings), TorControl(settings))
    try:
        yield network
    finally:
        await network.close()
