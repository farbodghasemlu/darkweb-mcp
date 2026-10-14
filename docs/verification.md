# Verification record
Checked on 2026-10-14 with Python 3.12.3 and Tor 0.4.9.11.
| Check | Result |
| --- | --- |
| Unit, parser, transport, leak, service, stdio and schema tests | 67 passed |
| Integration against a temporary onion on a private local Tor network | 1 passed |
| Ruff | Passed |
| Frozen dependency lock check | Passed |
| Source distribution and wheel builds | Passed |
| Docker image build and Compose configuration | Passed |
| MCP client connected to the hardened Compose server | Five tools and two resources exposed |
| Tor health through the isolated server network | Connected, bootstrap 100% |
| Clearnet fetch attempted through the container MCP client | Rejected with `INVALID_ONION` |
| Filtering disabled through the container CLI | Reported `content_filter=false` |
| Parser under the hardened container | Completed with network-denial rules active |
The private integration runner used pinned Chutney, three authorities, five relays, one client, and only local fixture content. It verified HTTP status, text extraction, links, caching, and a reported Tor circuit ID. Stem emitted two deprecation warnings for its thread API.
Public engine homepage checks timed out. Live parser compatibility and six operator address confirmations remain unverified; see [engine verification](engines.md). The checked image is tagged `onion-search-mcp:local`; distribution artifacts are in `dist/`.
