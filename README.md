# darkweb-mcp (onion-search-mcp)
A local Python stdio MCP server for searching onion services and reading pages through Tor. It provides five tools, eight search adapters, memory caches, and two MCP resources.

> [!IMPORTANT]
> **Privacy:** Use a local model for sensitive searches. Cloud models may receive your queries and fetched content through the MCP client. Check the client's logging, telemetry, and cloud fallback settings.

> [!WARNING]
> **User responsibility:** You are responsible for your actions and compliance with applicable laws. The authors and contributors disclaim liability for use or misuse of this software to the extent permitted by law.

## Run
The two-container setup gives the MCP process an internal Docker network. Only the Tor container has an external route.
```sh
docker compose build
docker compose up -d tor
docker compose run --rm --no-deps -T server
```
Wait for `docker compose ps` to show Tor as healthy before starting the server. The server uses stdin and stdout for MCP messages. Keep stdout attached to the client.
For a single container with Tor included:
```sh
docker run -i --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,noexec,nosuid,size=96m,uid=10001,gid=10001,mode=1770 --memory 768m --cpus 2 onion-search-mcp:local
```
The bundled container has an external route because Tor needs one. Use Compose for network isolation between the server and Tor. Initial Tor bootstrap can take several minutes.
For a local Python installation on Linux, install Tor and `libseccomp2`, then:
```sh
uv sync --frozen
uv run onion-search-mcp --bundled-tor
```
To use an existing Tor process, configure `SocksPort 9050 IsolateSOCKSAuth`, `ControlPort 9051`, and control authentication, then run `uv run onion-search-mcp`. Set `TOR_CONTROL_PASSWORD` or `TOR_COOKIE_FILE` if needed.
## Content filtering switch
Filtering is enabled by default. Turn it off or on for the process with either environment configuration or CLI options:
```sh
CONTENT_FILTER=false uv run onion-search-mcp
uv run onion-search-mcp --no-content-filter
uv run onion-search-mcp --content-filter
CONTENT_FILTER=false docker compose run --rm --no-deps -T server
```
Each content tool also accepts `content_filter`. Pass `false` to disable filtering for that call, `true` to enable it, or omit it to use the process setting.
```json
{"name":"onion_fetch","arguments":{"url":"http://YOUR_56_CHARACTER_ADDRESS.onion/","content_filter":false}}
```
The switch controls domain blocklists and keyword rules. Tor routing, URL validation, text-only retrieval, parser limits, and untrusted-content wrapping always apply. Search engines may apply their own filtering. Cache entries are separated by filter setting.
## MCP client configuration
Start the Tor sidecar with `docker compose up -d tor`, then configure a stdio client:
```json
{
  "mcpServers": {
    "onion-search": {
      "command": "docker",
      "args": ["compose", "--project-directory", "/absolute/path/to/onion", "run", "--rm", "--no-deps", "-T", "server"]
    }
  }
}
```
For the bundled image, use `docker run -i --rm onion-search-mcp:local` as the command and arguments. For Python, use `uv --directory /absolute/path/to/onion run --frozen onion-search-mcp`. Tool approval is configured in the client.
## Tools
| Tool | Arguments | Output |
| --- | --- | --- |
| `onion_search` | `query`, `engines`, `limit=20`, `page=1`, `content_filter` | Ranked results, agreement, source records, failed engines |
| `onion_fetch` | `url`, `max_chars=20000`, `include_links=true`, `content_filter` | Markdown text, title, links, response metadata |
| `onion_status` | `url`, `timeout_s=30`, `content_filter` | Reachability, HTTP status, latency, error code |
| `onion_links` | `url`, `onion_only=true`, `content_filter` | Onion and optional clearnet links, without following them |
| `tor_health` | none | SOCKS handshake, bootstrap percentage, Tor version |
`onion://engines` lists enabled adapters, addresses, verification state, and latest observed health. `onion://history` contains the last 100 queries in this process. Both are memory resources.
Sources include the engine, URL, UTC fetch time, and circuit ID when Tor reports one. A missing circuit ID is `null`. Cached sources retain the original fetch time. `up=true` means an HTTP response was received, including 4xx and 5xx responses. `exit_check=false` means no clearnet exit check was performed; onion services use no exit relay.
Search queries are trimmed and capped at 256 characters. Limits are 1 to 50 results, pages 1 to 10000, fetch text 1 to 200000 characters, and status timeout 1 to 120 seconds. Only HTTP(S) URLs with a 56-character base32 onion host are accepted. Credentials, v2 hosts, IP hosts, other schemes, and clearnet redirects are rejected.
Non-text responses return metadata and `UNSUPPORTED_CONTENT` without consuming their body. Blocked fetches return `blocked=true` and empty content. Blocked results and outbound links are omitted. Required keyword matches suppress a whole page. Known blocked domains inside returned text are redacted.
## Configuration
| Variable | Default | Purpose |
| --- | --- | --- |
| `TOR_SOCKS` | `127.0.0.1:9050` | Numeric proxy IP and port; no local DNS |
| `TOR_CONTROL` | `127.0.0.1:9051` | Numeric control IP and port |
| `TOR_CONTROL_PASSWORD` | unset | Control password; Compose provides a local default |
| `TOR_COOKIE_FILE` | unset | SAFECOOKIE authentication file |
| `TOR_BRIDGES` | empty | Bridge lines separated by newlines or semicolons |
| `ENGINES` | `all` | Comma-separated configured engine identifiers |
| `ENGINES_FILE` | `engines.yaml` | Engine configuration, with packaged fallback |
| `BLOCKLIST_PATHS` | `blocklists/csam.txt` | Comma-separated plain-domain or MD5 blocklists |
| `CONTENT_FILTER` | `true` | Default for all content tools |
| `TERMS_FILE` | `blocklists/terms.txt` | Required term list, with packaged fallback |
| `KEYWORD_FILTER` | `false` | Enable additional keyword rules |
| `FILTER_KEYWORDS` | empty | Additional comma-separated literal terms |
| `MAX_FETCH_BYTES` | `5242880` | Limit on raw and decompressed response bytes |
| `CACHE_TTL_S` | `900` | Search TTL; zero disables both caches |
| `FETCH_CACHE_TTL_S` | `600` | Fetch TTL |
| `CACHE_MAX_ENTRIES` | `128` | Maximum entries per cache |
| `CACHE_MAX_BYTES` | `33554432` | Maximum serialized bytes per cache |
| `ENGINE_RATE_LIMIT_S` | `3` | Minimum interval per engine |
| `JITTER_S` | `2` | Maximum randomized fan-out delay |
| `ENGINE_TIMEOUT_S` | `25` | Per-engine deadline |
| `SEARCH_TIMEOUT_S` | `40` | Whole fan-out deadline |
| `REQUEST_TIMEOUT_S` | `40` | Total request deadline |
| `LOG_QUERIES` | `false` | `true` is rejected; no disk history |
All eight adapters are enabled: `ahmia`, `torch`, `haystak`, `onionland`, `tor66`, `excavator`, `deep_search`, `onion_search_engine`. Addresses and request parameters live in YAML. Edit that file and rebuild the image to change container defaults; no host directories are mounted.
Verify current addresses against each operator's published address before use. `--verify-engines` checks reachability through Tor. It cannot establish operator identity. See [engine verification](docs/engines.md) for the evidence and current limitations.
The blocklist is a snapshot. There are no automatic downloads or update checks. See [blocklist provenance](blocklists/README.md) for its source and refresh procedure.
Bridges are configured in the Tor container through `TOR_BRIDGES`. obfs4 and Snowflake executables are included. Supply current bridge lines from a trusted source, then recreate the sidecar.
## Privacy and limits
All HTTP requests use remote DNS through SOCKS, with credentials derived from a random process session and each destination. Tor must use `IsolateSOCKSAuth`. A SOCKS credential separates streams but does not guarantee a new physical circuit for every request. `NEWNYM` is requested at shutdown; Tor may rate limit that signal.
The HTTP client stores no cookies and sends no Referer. It performs GET requests only. It does not execute JavaScript, submit forms, follow links automatically, render images, or decode media. Responses are streamed with byte limits and read and total deadlines. Redirect targets are validated before a request is made.
HTML parsing runs in a separate Linux process with a 384 MiB address-space limit, 8 seconds of CPU, a 10-second deadline, and seccomp rules that deny network syscalls. Scripts, styles, comments, embedded objects, and hidden elements are removed. Untrusted text is wrapped with a fresh delimiter. These measures do not prove that a page contains no prompt injection or that a link is legitimate.
Query history and caches stay in memory and are cleared on shutdown. No telemetry, query logging, disk cache, or runtime update checks are implemented. The MCP client and model runtime have their own storage and network behavior; see the privacy notice above.
Blocklists and literal keywords do not detect all abusive content. Links are research leads; engine agreement is a ranking signal.
## Development
```sh
uv sync --frozen
uv run ruff check .
uv run pytest -q -m 'not integration'
docker compose config --quiet
uv build
```
The unit suite uses saved parser fixtures and a local SOCKS simulator. The leak test stops the proxy and asserts that connections target only the local proxy, with no destination DNS or direct HTTP connection. CI runs integration on a private local Tor network. The test publishes a temporary onion service containing only fixtures. It never queries public search engines or reads third-party onion pages.
```sh
uv run python tests/integration/run.py
```
An existing test Tor instance can be supplied with `TEST_TOR_SOCKS` and `TEST_TOR_CONTROL`. Integration requires a usable Tor circuit and can fail when the network is unavailable. See [testing](docs/testing.md).
Stable errors include `TOR_UNAVAILABLE`, `INVALID_ONION`, `BLOCKED`, `TIMEOUT`, `ALL_ENGINES_FAILED`, `UNSUPPORTED_CONTENT`, `INVALID_QUERY`, `INVALID_ENGINE`, `INVALID_INPUT`, `CONFIG_ERROR`, `RESPONSE_TOO_LARGE`, `REDIRECT_LIMIT`, `PARSE_FAILED`, and `PARSE_TIMEOUT`. Tool errors contain scrubbed code and message JSON. Partial searches include per-engine codes and return completed results.

## License

MIT. See [LICENSE](LICENSE).
