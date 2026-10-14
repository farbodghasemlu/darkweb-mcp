import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode
import pytest
from onion_search_mcp.engines import merge
from onion_search_mcp.errors import OnionError
from onion_search_mcp.models import RawResult, Source
from onion_search_mcp.safety import ContentFilter
from onion_search_mcp.service import OnionService
from conftest import A, B, C
def row(engine, url=A, rank=1, title="Title", snippet="Snippet"):
    return RawResult(title=title, url=url, snippet=snippet, rank=rank, source=Source(engine=engine, url=A + "/search"))
def adapter(rows=None, error=None, delay=0):
    async def search(*args):
        await asyncio.sleep(delay)
        if error:
            raise error
        return rows or []
    return SimpleNamespace(search=search, last_health=None, last_source=Source(engine="fixture", url=A), config=SimpleNamespace(url=A))
def test_merge_agreement_normalization_and_best_rank(settings):
    results = merge({"a": [row("a", A + "/?utm_source=x", 5), row("a", A, 2, "Longer title")], "b": [row("b", A, 1, snippet="Longest snippet")]}, ContentFilter(settings), None)
    assert len(results) == 1 and results[0].score == 40 and results[0].engines == ["a", "b"]
    assert results[0].title == "Longer title" and results[0].snippet == "Longest snippet" and not results[0].verified
def test_filtering_happens_before_aggregation(settings):
    groups = {"a": [row("a", B), row("a", C, title="CSAM"), row("a", A)]}
    filtering = ContentFilter(settings)
    assert len(merge(groups, filtering, True)) == 1
    assert len(merge(groups, filtering, False)) == 3
async def test_partial_results_timeouts_cache_and_history(settings):
    service = OnionService(settings)
    settings.engine_timeout_s = 0.03
    service.engines = {"good": adapter([row("good")]), "bad": adapter(error=OnionError("TIMEOUT", "Unavailable")), "slow": adapter(delay=1)}
    try:
        result = await service.search("  research  ")
        assert result["failed_engines"] == ["bad", "slow"] and result["engine_errors"]["slow"] == "TIMEOUT"
        assert len(result["results"]) == 1
        assert service.history[-1]["query"] == "research"
        service.engines = {"good": adapter([row("good")])}
        first = await service.search("research")
        service.engines["good"].search = AsyncMock(side_effect=AssertionError("Cache missed"))
        cached = await service.search("research", limit=1)
        assert not first["cached"] and cached["cached"]
        assert service.history_resource()["memory_only"]
    finally:
        await service.close()
    assert not service.history and not service.search_cache.items
async def test_filter_override_cannot_reuse_other_cache(settings):
    service = OnionService(settings)
    service.engines = {"fixture": adapter([row("fixture", B)])}
    try:
        assert not (await service.search("test", content_filter=True))["results"]
        assert len((await service.search("test", content_filter=False))["results"]) == 1
        assert not (await service.search("test", content_filter=True))["results"]
    finally:
        await service.close()
async def test_all_failed_and_invalid_inputs(settings):
    service = OnionService(settings)
    service.engines = {"bad": adapter(error=OnionError("TIMEOUT", "Unavailable"))}
    try:
        with pytest.raises(OnionError, match="ALL_ENGINES_FAILED"):
            await service.search("test")
        with pytest.raises(OnionError, match="INVALID_QUERY"):
            await service.search("   ")
        with pytest.raises(OnionError, match="INVALID_ENGINE"):
            await service.search("test", engines=[])
        with pytest.raises(OnionError, match="INVALID_ENGINE"):
            await service.search("test", engines=["missing"])
    finally:
        await service.close()
async def test_whole_fanout_timeout_keeps_finished_results(settings):
    settings.search_timeout_s = 0.03
    service = OnionService(settings)
    service.engines = {"good": adapter([row("good")]), "slow": adapter(delay=1)}
    try:
        result = await service.search("test")
        assert len(result["results"]) == 1 and result["failed_engines"] == ["slow"]
    finally:
        await service.close()
async def test_fetch_links_blocking_switch_and_metadata(settings, socks):
    socks.routes["/page"] = (200, {"Content-Type": "text/html"}, (Path(__file__).parent / "fixtures/page.html").read_bytes())
    service = OnionService(settings)
    try:
        blocked = await service.fetch(B)
        assert blocked["blocked"] and not socks.requests
        assert not (await service.fetch(B, content_filter=False))["blocked"]
        response = await service.fetch(A + "/page", max_chars=10)
        assert response["truncated"] and "<untrusted_page" in response["text"]
        assert (await service.fetch(A + "/page", include_links=False))["links"] == []
        links = await service.links(A + "/page", onion_only=False)
        assert len(links["onion_links"]) == 2 and len(links["clearnet_links"]) == 1 and links["count"] == 3
        assert len((await service.links(A + "/page"))["clearnet_links"]) == 0
        status = await service.status(A + "/page")
        assert status["up"] and status["http_status"] == 200
        socks.routes["/media"] = (200, {"Content-Type": "application/zip"}, b"binary")
        assert (await service.fetch(A + "/media"))["code"] == "UNSUPPORTED_CONTENT"
        socks.routes["/filtered"] = (200, {"Content-Type": "text/plain"}, b"CSAM")
        assert (await service.fetch(A + "/filtered"))["blocked"]
        assert "CSAM" in (await service.fetch(A + "/filtered", content_filter=False))["text"]
    finally:
        await service.close()
async def test_all_eight_adapters_fanout_through_socks(settings, socks):
    service = OnionService(settings)
    fixtures = Path(__file__).parent / "fixtures"
    combined = b"".join((fixtures / f"{key}.html").read_bytes() for key in service.engines)
    for engine in service.engines.values():
        cfg = engine.config
        params = {**cfg.extra_params, cfg.query_param: "reporting", cfg.page_param: "1"}
        socks.routes[f"{cfg.search_path}?{urlencode(params)}"] = (200, {"Content-Type": "text/html"}, combined)
    try:
        result = await service.search("reporting")
        assert result["failed_engines"] == [] and len(result["results"]) >= 1
        assert len(socks.requests) == 8
        assert all(x["source"] and not x["verified"] for x in result["results"])
        assert len({x[0] for x in socks.credentials}) == 8
    finally:
        await service.close()
