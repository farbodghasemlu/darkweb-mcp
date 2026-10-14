import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from selectolax.parser import HTMLParser
from .errors import OnionError
from .urls import normalized_url
AD = re.compile(r"(?:^|[\s_-])(ad|ads|advert|advertisement|sponsored|banner|premium)(?:$|[\s_-])", re.I)
def clean_tree(body: str) -> HTMLParser:
    tree = HTMLParser(body)
    for node in tree.css("script,style,noscript,template,iframe,object,embed,svg,canvas,head link,meta,img,video,audio,source"):
        node.decompose()
    for node in list(tree.root.traverse(include_text=True)) if tree.root else []:
        if node.tag == "-comment":
            node.decompose()
            continue
        attrs = node.attributes
        style = re.sub(r"\s+", "", attrs.get("style", "")).lower()
        hidden_class = set(attrs.get("class", "").lower().split()) & {"hidden", "d-none", "invisible", "visually-hidden", "sr-only"}
        if "hidden" in attrs or hidden_class or attrs.get("aria-hidden", "").lower() == "true" or any(x in style for x in ("display:none", "visibility:hidden", "opacity:0")):
            node.decompose()
    return tree
def target(href: str, base: str) -> str | None:
    value = urljoin(base + "/", href)
    p = urlsplit(value)
    if p.hostname == urlsplit(base).hostname:
        params = parse_qs(p.query)
        for key in ("redirect_url", "url", "u", "l", "target", "redirect", "link"):
            if params.get(key):
                value = unquote(params[key][0])
                break
    try:
        return normalized_url(value)
    except OnionError:
        return None
def sponsored(node) -> bool:
    parent = node
    for _ in range(6):
        if not parent or parent.tag in {"body", "html"}:
            break
        attrs = parent.attributes
        if AD.search(attrs.get("class", "")) or AD.search(attrs.get("id", "")) or attrs.get("data-sponsored", "").lower() in {"true", "1"}:
            return True
        if parent.css_first(".sponsored,.ad-label,[data-ad]"):
            return True
        parent = parent.parent
    return False
class EngineParser:
    rows = ".result"
    title = "h3 a,h2 a,h4 a,a.result-title,a"
    snippet = ".snippet,.description,p"
    def parse(self, body: str, base: str):
        tree, results, seen = clean_tree(body), [], set()
        for row in tree.css(self.rows):
            if sponsored(row):
                continue
            anchor = row.css_first(self.title)
            if not anchor:
                continue
            href = anchor.attributes.get("href", "")
            if urlsplit(href).path.startswith("/ads/"):
                continue
            url = target(href, base)
            if not url or url in seen or urlsplit(url).hostname == urlsplit(base).hostname:
                continue
            seen.add(url)
            description = row.css_first(self.snippet)
            results.append({"title": anchor.text(separator=" ", strip=True)[:1024] or url, "url": url,
                            "snippet": description.text(separator=" ", strip=True)[:4096] if description else "", "rank": len(results) + 1})
            if len(results) >= 500:
                break
        return results
class AhmiaParser(EngineParser):
    rows = "#ahmiaResults .result,.results .result,li.result"
    snippet = "p,.snippet"
class TorchParser(EngineParser):
    rows = ".result,.search-result,table.result,tr.result"
    title = "h3 a,h2 a,.title a,a.result-title,td a,a"
    snippet = ".description,.snippet,td.description,p"
class HaystakParser(EngineParser):
    rows = ".result,.search-result"
    title = ".result-title a,.title a,h3 a,a"
    snippet = ".result-desc,.description,.snippet,p"
class OnionLandParser(EngineParser):
    rows = ".search-result,.result,.result-block"
    title = ".search-result-title a,h3 a,.title a,a"
    snippet = ".search-result-description,.description,.snippet,p"
class Tor66Parser(EngineParser):
    rows = ".result,.search-result,.search_result,body > b,body > div > b"
    title = "h3 a,h2 a,.title a,a"
class ExcavatorParser(EngineParser):
    rows = ".result,.search-result,.search_result"
    title = "h3 a,h2 a,.result-title a,a"
class DeepSearchParser(EngineParser):
    rows = ".result,.search-result,.results-item"
    title = "h3 a,h2 a,.title a,a"
class OnionSearchEngineParser(EngineParser):
    rows = ".result,.search-result,.search_result,table tr"
    title = "h3 a,h2 a,.title a,a"
PARSERS = {"ahmia": AhmiaParser, "torch": TorchParser, "haystak": HaystakParser, "onionland": OnionLandParser,
           "tor66": Tor66Parser, "excavator": ExcavatorParser, "deep_search": DeepSearchParser, "onion_search_engine": OnionSearchEngineParser}
