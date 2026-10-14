from onion_search_mcp.cache import MemoryCache
def test_expiry_and_copy_isolation(monkeypatch):
    clock = [100]
    monkeypatch.setattr("onion_search_mcp.cache.time.monotonic", lambda: clock[0])
    cache = MemoryCache(5, 2, 1024)
    value = {"items": [1]}
    cache.put("a", value)
    value["items"].append(2)
    copy = cache.get("a")
    copy["items"].append(3)
    assert cache.get("a") == {"items": [1]}
    clock[0] += 5
    assert cache.get("a") is None and cache.size == 0
def test_lru_size_limit_and_disable():
    cache = MemoryCache(10, 2, 100)
    cache.put("a", "1")
    cache.put("b", "2")
    cache.get("a")
    cache.put("c", "3")
    assert cache.get("b") is None and cache.get("a") == "1"
    cache.put("large", "x" * 101)
    assert cache.get("large") is None
    cache.clear()
    assert not cache.items and cache.size == 0
    cache = MemoryCache(0, 2, 100)
    cache.put("a", "b")
    assert cache.get("a") is None
