import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from .errors import OnionError
class TorRuntime:
    def __init__(self, settings, exposed: bool = False):
        self.settings, self.exposed, self.process, self.directory = settings, exposed, None, None
    def config(self, directory: str):
        address = "0.0.0.0" if self.exposed else "127.0.0.1"
        password = self.settings.tor_control_password or secrets.token_hex(32)
        self.settings.tor_control_password = password
        result = subprocess.run(["tor", "--hash-password", password], capture_output=True, text=True, check=True)
        hashed = next(x for x in result.stdout.splitlines() if x.startswith("16:"))
        lines = [f"DataDirectory {directory}/data", f"SocksPort {address}:9050 IsolateSOCKSAuth", f"ControlPort {address}:9051",
                 f"HashedControlPassword {hashed}", "AvoidDiskWrites 1", "SafeLogging 1", "Log err stderr", "ClientOnly 1", "ClientUseIPv6 0"]
        bridges = [x.strip() for x in self.settings.tor_bridges.replace(";", "\n").splitlines() if x.strip()]
        if bridges:
            if any("\r" in x or len(x) > 4096 for x in bridges):
                raise OnionError("CONFIG_ERROR", "Invalid bridge configuration.")
            lines += ["UseBridges 1", "ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy", "ClientTransportPlugin snowflake exec /usr/bin/snowflake-client"]
            lines += [f"Bridge {x.removeprefix('Bridge ')}" for x in bridges]
        return "\n".join(lines) + "\n"
    def start(self):
        self.directory = tempfile.mkdtemp(prefix="onion-tor-")
        try:
            Path(self.directory, "torrc").write_text(self.config(self.directory))
            self.process = subprocess.Popen(["tor", "-f", f"{self.directory}/torrc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            self.close()
            raise OnionError("TOR_UNAVAILABLE", "Tor could not start. Check that Tor is installed and its ports are available.") from None
        return self.process
    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = None
    def run(self):
        import signal
        process = self.start()
        def stop(*args):
            self.close()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            return process.wait()
        finally:
            self.close()
