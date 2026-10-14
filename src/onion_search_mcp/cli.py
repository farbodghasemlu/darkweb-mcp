import argparse
import asyncio
import json
import logging
import sys
from .config import Settings
from .errors import OnionError
from .service import OnionService
from .tor_runtime import TorRuntime
async def check(settings, verify: bool):
    service = OnionService(settings)
    await service.start()
    try:
        health = await service.health()
        if verify and health["connected"]:
            await asyncio.gather(*(engine.healthy() for engine in service.engines.values()))
        print(json.dumps({"tor": health, **service.engine_resource()}, indent=2))
        return 0 if health["connected"] else 1
    finally:
        await service.close()
def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(prog="onion-search-mcp")
    parser.add_argument("--stdio", action="store_true", help="Run the stdio MCP server using the configured Tor proxy")
    parser.add_argument("--content-filter", action=argparse.BooleanOptionalAction, default=None, help="Enable or disable domain and keyword content filtering")
    parser.add_argument("--bundled-tor", action="store_true", help="Start a private local Tor process")
    parser.add_argument("--tor-only", action="store_true", help="Run only Tor for the Compose sidecar")
    parser.add_argument("--check", action="store_true", help="Print Tor health and configuration, then exit")
    parser.add_argument("--verify-engines", action="store_true", help="Check each engine through Tor and print health")
    args = parser.parse_args()
    runtime = None
    try:
        settings = Settings()
        if args.content_filter is not None:
            settings.content_filter = args.content_filter
        if args.tor_only:
            return TorRuntime(settings, exposed=True).run()
        if args.bundled_tor:
            settings.tor_socks, settings.tor_control = "127.0.0.1:9050", "127.0.0.1:9051"
            runtime = TorRuntime(settings)
            runtime.start()
            asyncio.run(wait_for_tor(runtime, settings))
        if args.check or args.verify_engines:
            return asyncio.run(check(settings, args.verify_engines))
        from .server import create_server
        create_server(settings).run(transport="stdio")
        return 0
    except OnionError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print(json.dumps({"code": "CONFIG_ERROR", "message": "Startup failed. Check configuration and local Tor availability."}), file=sys.stderr)
        return 1
    finally:
        if runtime:
            runtime.close()
async def wait_for_tor(runtime, settings):
    from .control import TorControl
    control = TorControl(settings)
    try:
        async with asyncio.timeout(180):
            while runtime.process.poll() is None:
                if (await control.health())["connected"]:
                    return
                await asyncio.sleep(1)
    except TimeoutError:
        pass
    finally:
        await control.close()
    raise OnionError("TOR_UNAVAILABLE", "Tor did not finish bootstrapping within 180 seconds.")
if __name__ == "__main__":
    sys.exit(main())
