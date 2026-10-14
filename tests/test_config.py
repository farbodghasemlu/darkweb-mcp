import pytest
from onion_search_mcp.config import Settings
from onion_search_mcp.engines import load_engines
from onion_search_mcp.errors import OnionError
from onion_search_mcp.tor_runtime import TorRuntime
def test_environment_switch_and_no_disk_logging(monkeypatch):
    monkeypatch.setenv("CONTENT_FILTER", "false")
    assert Settings().content_filter is False
    monkeypatch.setenv("CONTENT_FILTER", "true")
    assert Settings().content_filter is True
    with pytest.raises(ValueError):
        Settings(log_queries=True)
def test_invalid_engine_config_has_scrubbed_error(settings, tmp_path):
    file = tmp_path / "engines.yaml"
    file.write_text("engines:\n  ahmia:\n    url: https://example.com/secret\n")
    settings.engines_file = str(file)
    with pytest.raises(OnionError, match="CONFIG_ERROR") as error:
        load_engines(settings, None, None)
    assert "secret" not in str(error.value)
def test_bridge_configuration_and_isolation(settings, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("onion_search_mcp.tor_runtime.subprocess.run", lambda *args, **kwargs: SimpleNamespace(stdout="16:HASH\n"))
    settings.tor_bridges = "obfs4 192.0.2.1:443 ABC cert=XYZ iat-mode=0;snowflake 192.0.2.3:80"
    config = TorRuntime(settings).config("/tmp/example")
    assert "IsolateSOCKSAuth" in config and "UseBridges 1" in config and config.count("\nBridge ") == 2
    assert "HashedControlPassword 16:HASH" in config and "SafeLogging 1" in config
