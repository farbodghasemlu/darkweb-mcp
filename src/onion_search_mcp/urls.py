import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from .errors import OnionError
HOST = re.compile(r"[a-z2-7]{56}\.onion\Z", re.I)
ONIONS = re.compile(r"(?:https?://)?(?:[a-z2-7]{56}\.)?([a-z2-7]{56}\.onion)(?::\d+)?[^\s<>\[\]\"']*", re.I)
TRACKING = {"fbclid", "gclid", "dclid", "msclkid", "ref", "referrer", "source", "mc_cid", "mc_eid"}
def onion_url(value: str) -> str:
    try:
        if len(value) > 8192 or any(ord(c) < 33 or ord(c) == 127 for c in value) or "\\" in value:
            raise ValueError
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or not HOST.fullmatch(p.hostname or "") or p.username or p.password:
            raise ValueError
        port = p.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        host = p.hostname.lower()
        authority = host if port in {None, 80 if p.scheme == "http" else 443} else f"{host}:{port}"
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
        return urlunsplit((p.scheme, authority, p.path, urlencode(q), ""))
    except (ValueError, TypeError, AttributeError):
        raise OnionError("INVALID_ONION", "Use http or https with a 56-character v3 onion host. v2 addresses, credentials and other hosts are rejected.") from None
def normalized_url(value: str) -> str:
    p = urlsplit(onion_url(value))
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip("/"), p.query, ""))
def safe_link(value: str) -> str | None:
    try:
        p = urlsplit(value)
        if p.hostname and p.hostname.lower().endswith(".onion"):
            return onion_url(value)
        if p.scheme in {"http", "https"} and p.hostname and not p.username and not p.password and not any(ord(c) < 33 for c in value):
            return urlunsplit((p.scheme, p.netloc.lower(), p.path, p.query, ""))
    except (ValueError, OnionError):
        pass
    return None
