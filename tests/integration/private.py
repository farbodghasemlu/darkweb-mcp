import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from stem.control import Controller
ROOT = Path(__file__).resolve().parents[2]
PIN = "62b54a55215c94eb14adc22c5acd17b2ada04b76"
async def bootstrap():
    async with asyncio.timeout(180):
        while True:
            try:
                with Controller.from_port(port=8008) as control:
                    control.authenticate()
                    if "PROGRESS=100" in control.get_info("status/bootstrap-phase", ""):
                        return
            except Exception:
                pass
            await asyncio.sleep(1)
def main():
    chutney = Path(os.environ.get("CHUTNEY_PATH", "/tmp/onion-chutney")).resolve()
    if not (chutney / "chutney").is_file():
        raise SystemExit("Set CHUTNEY_PATH to the pinned Chutney checkout described in docs/testing.md")
    commit = subprocess.check_output(["git", "-C", str(chutney), "rev-parse", "HEAD"], text=True).strip()
    if commit != PIN:
        raise SystemExit("Chutney checkout does not match the pinned test revision")
    python = os.environ.get("CHUTNEY_PYTHON") or subprocess.check_output(["uv", "python", "find", "3.11"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="onion-private-network-") as directory:
        network = Path(directory, "network")
        network.write_text('Authority=Node(tag="a",authority=1,relay=1,torrc="authority.tmpl")\nRelay=Node(tag="r",relay=1,exit=1,torrc="relay.tmpl")\nClient=Node(tag="c",client=1,torrc="client.tmpl")\nConfigureNodes(Authority.getN(3)+Relay.getN(5)+Client.getN(1))\n')
        env = {**os.environ, "PYTHON": python, "CHUTNEY_PATH": str(chutney), "CHUTNEY_DATA_DIR": f"{directory}/net", "CHUTNEY_START_TIME": "180"}
        command = [str(chutney / "chutney")]
        try:
            for action in ("configure", "start"):
                subprocess.run([*command, action, str(network)], env=env, cwd=chutney, check=True)
            asyncio.run(bootstrap())
            tests = {**os.environ, "TEST_TOR_SOCKS": "127.0.0.1:9008", "TEST_TOR_CONTROL": "127.0.0.1:8008"}
            tests.pop("TEST_TOR_PASSWORD", None)
            return subprocess.run([sys.executable, "tests/integration/run.py"], env=tests, cwd=ROOT).returncode
        finally:
            subprocess.run([*command, "stop", str(network)], env=env, cwd=chutney, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if __name__ == "__main__":
    sys.exit(main())
