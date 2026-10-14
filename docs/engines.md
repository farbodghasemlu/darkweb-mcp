# Engine verification
The runtime reads onion addresses from `engines.yaml` and accepts no clearnet engine endpoint. All eight adapters are enabled by default. Configure `ENGINES` to select a subset.
Ahmia's address was checked against its [operator homepage](https://ahmia.fi/) on 2026-10-14. Onion Search Engine's address was checked against its [operator homepage](https://onionsearchengine.com/) on the same date. Those entries carry `verification: operator-published`.
The other six entries are candidate addresses. An operator-published source could not be established during this build, so they carry `verification: needs-operator-verification`. Reachability does not authenticate an operator. No search result is labeled verified.
| Engine | Configuration ID | Address evidence | Live health check |
| --- | --- | --- | --- |
| Ahmia | `ahmia` | Operator homepage | Timed out |
| Torch | `torch` | Candidate, operator confirmation needed | Timed out |
| Haystak | `haystak` | Candidate, operator confirmation needed | Timed out |
| OnionLand Search | `onionland` | Candidate, operator confirmation needed | Timed out |
| Tor66 | `tor66` | Candidate, operator confirmation needed | Timed out |
| Excavator | `excavator` | Candidate, operator confirmation needed | Timed out |
| Deep Search | `deep_search` | Candidate, operator confirmation needed | Timed out |
| Onion Search Engine | `onion_search_engine` | Operator homepage | Timed out |
The live checks used a bootstrapped local Tor 0.4.9.11 instance on 2026-10-14 with a 10-second deadline. A separate 25-second request to Ahmia's onion homepage also timed out. These observations do not establish whether a service is offline.
The adapters have saved regression fixtures for their result containers, redirect links, descriptions, ads, clearnet entries, and v2 addresses. Fixtures are reconstructed HTML, not captures of live search results. Ahmia, Haystak, OnionLand, Tor66, and Onion Search Engine also include known legacy markup patterns drawn from the [OnionSearch adapter source](https://github.com/megadose/OnionSearch/blob/master/onionsearch/core.py). Current parser compatibility across all eight live services remains unverified.
Run a current check with:
```sh
uv run onion-search-mcp --verify-engines
```
Change `url`, `search_path`, `query_param`, `page_param`, or `extra_params` when an operator changes its interface. Keep a sanitized HTML sample in `tests/fixtures` and update the corresponding parser test. Sponsored rows and self-links are omitted. The parser extracts targets from engine redirect URLs without following those redirects.
