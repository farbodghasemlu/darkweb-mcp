import json
import re
import sys
from urllib.parse import urljoin
def limits():
    import resource
    for key, value in ((resource.RLIMIT_AS, 402653184), (resource.RLIMIT_CPU, 8), (resource.RLIMIT_FSIZE, 0), (resource.RLIMIT_NOFILE, 32)):
        resource.setrlimit(key, (value, value))
def deny_network():
    import ctypes
    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes, lib.seccomp_init.restype = [ctypes.c_uint32], ctypes.c_void_p
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    context = lib.seccomp_init(0x7fff0000)
    if not context:
        raise OSError("Parser isolation failed")
    try:
        for name in (b"socket", b"connect", b"bind", b"listen", b"accept", b"accept4", b"sendto", b"sendmsg"):
            syscall = lib.seccomp_syscall_resolve_name(name)
            if syscall >= 0 and lib.seccomp_rule_add(context, 0x00050001, syscall, 0):
                raise OSError("Parser isolation failed")
        if lib.seccomp_load(context):
            raise OSError("Parser isolation failed")
    finally:
        lib.seccomp_release(context)
def page(body: str, url: str, content_type: str, max_chars: int):
    if content_type not in {"text/html", "application/xhtml+xml"}:
        return {"title": "", "text": body[:max_chars], "links": [], "truncated": len(body) > max_chars}
    from trafilatura import extract
    from .engine_parsers import clean_tree
    from .urls import safe_link
    tree = clean_tree(body)
    title_node = tree.css_first("title")
    title = title_node.text(strip=True)[:1024] if title_node else ""
    links, seen = [], set()
    for anchor in tree.css("a[href]"):
        href = safe_link(urljoin(url, anchor.attributes["href"]))
        if href and href not in seen and len(links) < 2000:
            seen.add(href)
            links.append({"url": href, "text": anchor.text(separator=" ", strip=True)[:1024]})
    for node in tree.css("head,nav,footer,form,input,button,select,textarea"):
        node.decompose()
    text = extract(tree.html, output_format="markdown", include_comments=False, include_tables=True, include_links=False, favor_recall=True) or (tree.body.text(separator="\n", strip=True) if tree.body else "")
    heading = tree.css_first("h1")
    if heading and (label := heading.text(separator=" ", strip=True)) and label not in text:
        text = f"# {label}\n\n{text}"
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"title": title, "text": text[:max_chars], "links": links, "truncated": len(text) > max_chars}
def main():
    limits()
    deny_network()
    import socket
    def denied(*args, **kwargs):
        raise OSError("Parser network access is disabled")
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
    payload = json.loads(sys.stdin.buffer.read(83886080))
    if payload["mode"] == "page":
        result = page(payload["body"], payload["url"], payload["content_type"], payload["max_chars"])
    else:
        from .engine_parsers import PARSERS
        result = PARSERS[payload["engine"]]().parse(payload["body"], payload["url"])
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
if __name__ == "__main__":
    main()
