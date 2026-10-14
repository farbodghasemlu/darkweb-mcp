import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from onion_search_mcp.server import create_server
from conftest import ROOT
async def test_schema_exposes_five_tools_and_filter_switch():
    tools = await create_server().list_tools()
    assert {x.name for x in tools} == {"onion_search", "onion_fetch", "onion_status", "onion_links", "tor_health"}
    for tool in tools:
        assert tool.annotations.readOnlyHint
        if tool.name != "tor_health":
            assert "content_filter" in tool.inputSchema["properties"]
async def test_stdio_protocol_resources_and_scrubbed_error():
    params = StdioServerParameters(command=sys.executable, args=["-m", "onion_search_mcp"], cwd=str(ROOT), env={"TOR_SOCKS": "127.0.0.1:1", "TOR_CONTROL": "127.0.0.1:1"})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        assert len((await client.list_tools()).tools) == 5
        assert {str(x.uri) for x in (await client.list_resources()).resources} == {"onion://engines", "onion://history"}
        engines = await client.read_resource("onion://engines")
        assert len(json.loads(engines.contents[0].text)["engines"]) == 8
        result = await client.call_tool("onion_fetch", {"url": "https://example.com/private-query"})
        assert result.isError and "INVALID_ONION" in result.content[0].text and "private-query" not in result.content[0].text
        health = await client.call_tool("tor_health")
        assert not health.isError and "TOR_UNAVAILABLE" in health.content[0].text
