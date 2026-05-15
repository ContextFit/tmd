import json
from pathlib import Path

from tmd.mcp import MCPServerConfig, TMDMCPServer


def make_file(tmp_path: Path) -> Path:
    path = tmp_path / "invoices.tmd"
    path.write_text("""# Invoices

invoices[1]: name=Acme, amount=100, paid=false
invoices[2]: name=ExampleCo, amount=200, paid=true
""")
    return path


def tool_call(server: TMDMCPServer, name: str, arguments: dict):
    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    assert response["result"]["isError"] is False
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def test_mcp_initialize_and_tools_list(tmp_path):
    server = TMDMCPServer(MCPServerConfig(root=tmp_path))
    init = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "tmd"

    tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert {"tmd_list_files", "tmd_query_file", "tmd_append_row", "tmd_update_row"} <= names


def test_mcp_list_query_append_update(tmp_path):
    make_file(tmp_path)
    server = TMDMCPServer(MCPServerConfig(root=tmp_path))

    files = tool_call(server, "tmd_list_files", {})
    assert files["files"] == ["invoices.tmd"]

    result = tool_call(server, "tmd_query_file", {"path": "invoices.tmd", "query_text": "SUM(amount)"})
    assert result["result"] == 300

    appended = tool_call(server, "tmd_append_row", {"path": "invoices.tmd", "fields": {"name": "Northwind", "amount": 50, "paid": False}})
    assert appended["row"]["_id"] == 3

    updated = tool_call(server, "tmd_update_row", {"path": "invoices.tmd", "row_id": 3, "fields": {"paid": True}})
    assert updated["row"]["paid"] is True


def test_mcp_rejects_paths_outside_root(tmp_path):
    server = TMDMCPServer(MCPServerConfig(root=tmp_path))
    outside = tmp_path.parent / "outside.tmd"
    outside.write_text("# Outside\n")
    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "tmd_parse_file", "arguments": {"path": str(outside)}},
    })
    assert response["result"]["isError"] is True
    assert "outside TMD MCP root" in response["result"]["content"][0]["text"]
