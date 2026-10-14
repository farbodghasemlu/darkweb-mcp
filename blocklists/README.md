# Blocklist snapshot
`csam.txt` was downloaded from [Ahmia's published blocklist](https://ahmia.fi/blacklist/banned/) on 2026-10-14. It contains 60048 lines of MD5 hashes of onion domains. It does not contain page content or direct onion addresses.
SHA-256 of the file:
```text
bb50f70c0f176d2315cb1784543ce74b1cdf712981aaff1125f799933430b1ca
```
Ahmia's [server implementation](https://github.com/ahmia/ahmia-site/blob/master/ahmia/views.py) hashes each domain string with MD5. The local filter compares a lowercase `hostname.onion` string against these hashes. Custom lists may contain plain v3 onion domains, HTTP(S) onion URLs, or MD5 hashes, one per line. Blank lines and lines beginning with `#` are ignored.
To explicitly refresh the snapshot through a local Tor proxy:
```sh
curl --socks5-hostname 127.0.0.1:9050 --fail --max-time 120 http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/blacklist/banned/ -o blocklists/csam.txt.new
```
Validate the file before replacing the snapshot, update its hash here, and rebuild the image. Startup rejects missing, empty, or malformed blocklists. Updates are never automatic.
`terms.txt` contains four literal abuse-related terms. Extra keyword rules are configured with `KEYWORD_FILTER` and `FILTER_KEYWORDS`. `CONTENT_FILTER=false`, `--no-content-filter`, or a tool's `content_filter=false` override disables both domain and keyword filtering.
