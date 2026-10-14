import asyncio
import re
import threading
from stem import Signal
from stem.connection import authenticate_safecookie
from stem.control import Controller, EventType
from .models import Source
class TorControl:
    def __init__(self, settings):
        self.settings, self.controller, self.circuits = settings, None, {}
        self.lock = threading.Lock()
    def _connect(self):
        if self.controller and self.controller.is_alive():
            return self.controller
        host, port = self.settings.tor_control.rsplit(":", 1)
        controller = Controller.from_port(address=host.strip("[]"), port=int(port))
        try:
            if self.settings.tor_cookie_file:
                authenticate_safecookie(controller, self.settings.tor_cookie_file)
            else:
                controller.authenticate(password=self.settings.tor_control_password)
            controller.add_event_listener(self._stream, EventType.STREAM)
            controller.msg("SETEVENTS EXTENDED STREAM")
        except Exception:
            controller.close()
            raise
        self.controller = controller
        return controller
    def _stream(self, event):
        username = getattr(event, "socks_username", None) or event.keyword_args.get("SOCKS_USERNAME")
        circuit = getattr(event, "circ_id", None)
        if username and circuit and circuit != "0":
            with self.lock:
                self.circuits[username.strip('"')] = circuit
                if len(self.circuits) > 1024:
                    self.circuits.pop(next(iter(self.circuits)))
    async def start(self):
        try:
            await asyncio.wait_for(asyncio.to_thread(self._connect), 5)
        except Exception:
            pass
    def source(self, url: str | None, username: str | None, engine: str | None = None) -> Source:
        with self.lock:
            circuit = self.circuits.get(username)
        return Source(engine=engine, url=url, tor_circuit_id=circuit)
    def _health(self):
        c = self._connect()
        phase = c.get_info("status/bootstrap-phase", "")
        match = re.search(r"PROGRESS=(\d+)", phase)
        pct = int(match[1]) if match else 0
        return {"connected": pct == 100, "bootstrap_pct": pct, "tor_version": str(c.get_version()), "exit_check": False,
                "exit_check_note": "No external exit check is made. Onion traffic uses no exit relay."}
    async def health(self):
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._health), 5)
        except Exception:
            return {"connected": False, "bootstrap_pct": 0, "tor_version": None, "exit_check": False, "error": "TOR_UNAVAILABLE"}
    def _close(self):
        if self.controller:
            try:
                if self.controller.is_alive():
                    self.controller.signal(Signal.NEWNYM)
            except Exception:
                pass
            finally:
                self.controller.close()
                self.controller = None
        with self.lock:
            self.circuits.clear()
    async def close(self):
        await asyncio.to_thread(self._close)
