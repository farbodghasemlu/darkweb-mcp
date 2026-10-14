import pytest
from onion_search_mcp.errors import OnionError
from onion_search_mcp.urls import normalized_url, onion_url
from conftest import A
@pytest.mark.parametrize("url", ["https://example.com", "http://127.0.0.1", "http://[::1]", "file:///etc/passwd", "http://abcdefghijklmnop.onion",
                                f"http://user@{'a' * 56}.onion", A + ":0", A + ":65536", A + "\\@example.com", A + "\n", A + ".example.com", A.replace("http", "ftp")])
def test_rejects_non_onion_and_ambiguous_urls(url):
    with pytest.raises(OnionError, match="INVALID_ONION") as error:
        onion_url(url)
    assert url not in str(error.value)
def test_normalizes_results_without_changing_fetch_paths():
    url = A.upper().replace("HTTP", "http") + "/path/?utm_source=x&id=5&fbclid=y#fragment"
    assert normalized_url(url) == A + "/path?id=5"
    assert onion_url(url) == A + "/path/?id=5"
def test_retains_ports_and_query_values():
    assert normalized_url(A + ":8080/x?key=a%26b") == A + ":8080/x?key=a%26b"
