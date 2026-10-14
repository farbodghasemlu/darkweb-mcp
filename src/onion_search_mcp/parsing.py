import asyncio
import json
import os
import sys
from .errors import OnionError
class Parser:
    def __init__(self):
        self.gate = asyncio.Semaphore(2)
    async def communicate(self, process, payload):
        async def send():
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
        sender = asyncio.create_task(send())
        output = bytearray()
        try:
            while chunk := await process.stdout.read(65536):
                if len(output) + len(chunk) > 12582912:
                    raise OnionError("PARSE_FAILED", "The isolated parser exceeded its output limit.")
                output.extend(chunk)
            await sender
            await process.wait()
            return bytes(output)
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
    async def run(self, mode: str, body: str, url: str, **options):
        async with self.gate:
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "onion_search_mcp.parser_worker", stdin=asyncio.subprocess.PIPE,
                                                         stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                                                         env={k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "PYTHONPATH"}})
            try:
                payload = json.dumps({"mode": mode, "body": body, "url": url, **options}).encode()
                async with asyncio.timeout(10):
                    output = await self.communicate(process, payload)
                if process.returncode:
                    raise OnionError("PARSE_FAILED", "The isolated parser could not process the response.")
                return json.loads(output)
            except TimeoutError:
                raise OnionError("PARSE_TIMEOUT", "The isolated parser exceeded its time limit.") from None
            except (ValueError, OSError):
                raise OnionError("PARSE_FAILED", "The isolated parser could not process the response.") from None
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()
