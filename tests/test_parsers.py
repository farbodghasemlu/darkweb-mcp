from pathlib import Path
import subprocess
import sys
import pytest
from onion_search_mcp.engine_parsers import PARSERS
from onion_search_mcp.parsing import Parser
from conftest import A, C
FIXTURES = Path(__file__).parent / "fixtures"
@pytest.mark.parametrize("engine", list(PARSERS))
def test_saved_engine_fixtures(engine):
    rows = PARSERS[engine]().parse((FIXTURES / f"{engine}.html").read_text(), A)
    assert len(rows) == 2
    assert rows[0]["url"] == C + "/docs"
    assert rows[0]["title"] == "Research archive"
    assert rows[1]["title"] == "Public newsroom"
    assert [x["rank"] for x in rows] == [1, 2]
@pytest.mark.parametrize("engine", list(PARSERS))
def test_empty_or_malformed_markup_is_tolerated(engine):
    assert PARSERS[engine]().parse("<html><p>Nothing indexed", A) == []
async def test_page_parser_strips_active_hidden_and_comment_content():
    result = await Parser().run("page", (FIXTURES / "page.html").read_text(), A + "/article", content_type="text/html", max_chars=20000)
    assert result["title"] == "Public newsroom"
    assert "Research notes" in result["text"]
    for payload in ("ignore all", "hidden payload", "invisible payload", "comment payload", "hidden text"):
        assert payload not in result["text"]
    assert len(result["links"]) == 3
    assert any(x["url"] == A + "/relative" for x in result["links"])
async def test_page_parser_truncation_and_plaintext():
    result = await Parser().run("page", "abcdefgh", A, content_type="text/plain", max_chars=3)
    assert result == {"title": "", "text": "abc", "links": [], "truncated": True}
async def test_engine_parser_runs_in_child():
    result = await Parser().run("engine", (FIXTURES / "ahmia.html").read_text(), A, engine="ahmia")
    assert len(result) == 2
def test_parser_seccomp_denies_real_network_syscalls():
    code = 'from onion_search_mcp.parser_worker import deny_network; import socket; deny_network(); socket.socket()'
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode != 0 and "PermissionError" in result.stderr
