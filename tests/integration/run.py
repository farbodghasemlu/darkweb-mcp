import asyncio
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from stem.control import Controller
from onion_search_mcp.config import Settings
from onion_search_mcp.service import OnionService
ROOT = Path(__file__).resolve().parents[2]
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        body = b'<html><head><title>Local test service</title></head><body><main><h1>Private integration fixture</h1><p>This page belongs to this test run. It contains only local test data.</p><a href="/article">Local article</a><a href="https://example.com">Listed only</a></main></body></html>'
        self.send_response(404 if self.path == "/missing" else 200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
async def bootstrap(port, process):
    async with asyncio.timeout(300):
        while process.poll() is None:
            try:
                with Controller.from_port(port=port) as control:
                    control.authenticate()
                    if "PROGRESS=100" in control.get_info("status/bootstrap-phase", ""):
                        return
            except Exception:
                pass
            await asyncio.sleep(1)
    raise RuntimeError("Tor failed to bootstrap")
async def ready(url, socks, control_port):
    service = OnionService(Settings(tor_socks=socks, tor_control=f"127.0.0.1:{control_port}", tor_control_password=os.environ.get("TEST_TOR_PASSWORD")))
    try:
        for _ in range(4):
            if (await service.status(url, timeout_s=90))["up"]:
                return
            await asyncio.sleep(1)
        raise RuntimeError("The test onion service is not reachable")
    finally:
        await service.close()
def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    external = os.environ.get("TEST_TOR_CONTROL")
    process = None
    with tempfile.TemporaryDirectory(prefix="onion-integration-") as directory:
        socks, control_port = "127.0.0.1:19050", 19051
        if external:
            socks, control_port = os.environ["TEST_TOR_SOCKS"], int(external.rsplit(":", 1)[1])
        else:
            torrc = Path(directory, "torrc")
            torrc.write_text(f'DataDirectory {directory}/data\nSocksPort {socks} IsolateSOCKSAuth\nControlPort 127.0.0.1:{control_port}\nCookieAuthentication 1\nSafeLogging 1\nAvoidDiskWrites 1\nLog err stderr\n')
            process = subprocess.Popen(["tor", "-f", str(torrc)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if process:
                asyncio.run(bootstrap(control_port, process))
            with Controller.from_port(port=control_port) as control:
                control.authenticate(password=os.environ.get("TEST_TOR_PASSWORD"))
                service = control.create_ephemeral_hidden_service({80: server.server_address[1]}, key_content="ED25519-V3", await_publication=True, timeout=120)
                env = {**os.environ, "TEST_ONION_URL": f"http://{service.service_id}.onion", "TEST_TOR_SOCKS": socks, "TEST_TOR_CONTROL": f"127.0.0.1:{control_port}"}
                try:
                    asyncio.run(ready(env["TEST_ONION_URL"], socks, control_port))
                    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", "integration"], cwd=ROOT, env=env).returncode
                finally:
                    control.remove_ephemeral_hidden_service(service.service_id)
        finally:
            server.shutdown()
            server.server_close()
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
if __name__ == "__main__":
    sys.exit(main())
