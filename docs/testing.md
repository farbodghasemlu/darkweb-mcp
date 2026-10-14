# Testing
Unit tests use local data. The SOCKS simulator implements SOCKS5 authentication and remote destination addressing, then returns saved HTTP responses. It records destination names, credentials, GET headers, and requests so tests can check routing and privacy behavior.
The suite covers all eight parser fixtures, URL normalization, v2 and clearnet rejection, redirects, domain hashes, filtering switches, keyword rules, ranking, deduplication, partial failures, deadlines, caches, resource exposure, stdio tool errors, media rejection, compressed size limits, and stopped-Tor leaks.
```sh
uv run pytest -q -m 'not integration'
```
CI uses [Chutney](https://github.com/torproject/chutney/tree/62b54a55215c94eb14adc22c5acd17b2ada04b76) to start three local Tor authorities, five relays, and one client. No public Tor network is used for this test. Chutney is pinned to the linked revision and runs with Python 3.11.
```sh
uv python install 3.11
git clone https://github.com/torproject/chutney.git /tmp/onion-chutney
git -C /tmp/onion-chutney checkout 62b54a55215c94eb14adc22c5acd17b2ada04b76
uv run python tests/integration/private.py
```
Set `CHUTNEY_PATH` for another checkout location. The private network uses local ports in the 7000, 8000, and 9000 ranges and must run alone on those ports. Temporary keys and state are removed after shutdown.
The integration runner serves a fixture on a random loopback HTTP port, creates a temporary v3 onion service through the control port, waits for reachability, runs the integration tests, removes the onion service, and shuts down its processes. Its only target page belongs to the test run. Public engines and third-party onion pages are never queried. To test using public Tor instead, the runner can start its own Tor process on local ports 19050 and 19051:
```sh
uv run python tests/integration/run.py
```
To use an existing test Tor instance:
```sh
TEST_TOR_SOCKS=127.0.0.1:19050 TEST_TOR_CONTROL=127.0.0.1:19051 uv run python tests/integration/run.py
```
If its control port uses password authentication, add `TEST_TOR_PASSWORD`. The test asserts Tor health, HTTP reachability, extraction, grouped links, cache reuse, and circuit attribution. Public Tor bootstrap and onion descriptor availability can delay or prevent the test.
Docker configuration and parser hardening can be checked with:
```sh
docker compose config --quiet
docker build -t onion-search-mcp:local .
```
The production image runs as UID 10001. Compose supplies a read-only filesystem, tmpfs state, capability removal, resource limits, no Docker logging, and an internal-only server network. No host directory is mounted.
