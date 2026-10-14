import os
import pytest
from onion_search_mcp.config import Settings
from onion_search_mcp.service import OnionService
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not os.environ.get("TEST_ONION_URL"), reason="Run tests/integration/run.py or set TEST_ONION_URL for your own service")]
async def test_real_tor_to_our_own_onion():
    url = os.environ["TEST_ONION_URL"]
    service = OnionService(Settings(tor_socks=os.environ["TEST_TOR_SOCKS"], tor_control=os.environ["TEST_TOR_CONTROL"], tor_control_password=os.environ.get("TEST_TOR_PASSWORD")))
    await service.start()
    try:
        health = await service.health()
        assert health["connected"] and health["bootstrap_pct"] == 100
        status = await service.status(url, timeout_s=90)
        assert status["up"] and status["http_status"] == 200
        response = await service.fetch(url)
        assert response["title"] == "Local test service" and "Private integration fixture" in response["text"]
        assert response["source"]["tor_circuit_id"] is not None
        links = await service.links(url, onion_only=False)
        assert len(links["onion_links"]) == 1 and len(links["clearnet_links"]) == 1
        assert (await service.fetch(url))["cached"]
        assert (await service.status(url + "/missing"))["http_status"] == 404
    finally:
        await service.close()
