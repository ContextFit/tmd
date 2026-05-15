"""Minimal MCP stdio server for TMD files.

The server is dependency-free and implements the JSON-RPC subset needed by
Claude Desktop-style MCP clients. It is intentionally scoped to a filesystem
root so agents can work with explicit TMD files without a separate vault model.
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from tmd.ops import append_row, get_row, list_rows, update_row, validate_file
from tmd.parser import parse_file
from tmd.query import compute, query

MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class MCPServerConfig:
    root: Path
    max_files: int = 200
    max_rows: int = 100


class TMDMCPServer:
    """Serve TMD row/table operations as MCP tools."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.root = config.root.expanduser().resolve()

    def serve(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
            except Exception as exc:  # pragma: no cover - stdio boundary
                response = self._error_response(None, -32603, f"Internal error: {exc}")
                print(traceback.format_exc(), file=sys.stderr, flush=True)
            if response is not None:
                stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                stdout.flush()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return self._result_response(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tmd", "version": "0.1.0"},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return self._result_response(request_id, {})
        if method == "tools/list":
            return self._result_response(request_id, {"tools": self._tools()})
        if method == "tools/call":
            return self._handle_tool_call(request_id, params)

        if request_id is None:
            return None
        return self._error_response(request_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "tmd_list_files":
                result = self.list_files(**arguments)
            elif name == "tmd_parse_file":
                result = self.parse_file_tool(**arguments)
            elif name == "tmd_query_file":
                result = self.query_file(**arguments)
            elif name == "tmd_get_row":
                result = self.get_row_tool(**arguments)
            elif name == "tmd_append_row":
                result = self.append_row_tool(**arguments)
            elif name == "tmd_update_row":
                result = self.update_row_tool(**arguments)
            elif name == "tmd_validate_file":
                result = self.validate_file_tool(**arguments)
            else:
                return self._error_response(request_id, -32602, f"Unknown tool: {name}")
            return self._result_response(
                request_id,
                {"content": [{"type": "text", "text": self._json(result)}], "isError": False},
            )
        except Exception as exc:
            return self._result_response(
                request_id,
                {"content": [{"type": "text", "text": f"TMD tool error: {exc}"}], "isError": True},
            )

    def list_files(self, pattern: str = "**/*.tmd", max_files: int | None = None) -> dict[str, Any]:
        limit = max_files or self.config.max_files
        files = []
        for path in sorted(self.root.glob(pattern)):
            if path.is_file() and path.suffix == ".tmd":
                resolved = self._resolve_path(path)
                files.append(str(resolved.relative_to(self.root)))
                if len(files) >= limit:
                    break
        return {"root": str(self.root), "files": files, "count": len(files), "truncated": len(files) >= limit}

    def parse_file_tool(self, path: str, include_rows: bool = True, max_rows: int | None = None) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        doc = parse_file(file_path)
        rows = doc.to_dicts() if include_rows else []
        limit = max_rows or self.config.max_rows
        return {
            "path": str(file_path.relative_to(self.root)),
            "title": doc.title,
            "table_name": doc.table_name,
            "row_count": len(doc.rows),
            "schema": {"fields": doc.schema.fields, "computed": doc.schema.computed},
            "rows": rows[:limit],
            "truncated": include_rows and len(rows) > limit,
        }

    def query_file(self, path: str, query_text: str) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        doc = parse_file(file_path)
        result = query(doc, query_text)
        return {"path": str(file_path.relative_to(self.root)), "query": query_text, "result": self._normalize_result(result)}

    def get_row_tool(self, path: str, row_id: str | int) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        return {"path": str(file_path.relative_to(self.root)), "row": get_row(file_path, row_id)}

    def append_row_tool(self, path: str, fields: dict[str, Any], row_id: str | int | None = None, table: str | None = None) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        row = append_row(file_path, fields=fields, row_id=row_id, table=table)
        return {"path": str(file_path.relative_to(self.root)), "row": row}

    def update_row_tool(self, path: str, row_id: str | int, fields: dict[str, Any], replace: bool = False) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        row = update_row(file_path, row_id=row_id, fields=fields, replace=replace)
        return {"path": str(file_path.relative_to(self.root)), "row": row}

    def validate_file_tool(self, path: str) -> dict[str, Any]:
        file_path = self._resolve_path(path)
        result = validate_file(file_path)
        result["path"] = str(file_path.relative_to(self.root))
        return result

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.expanduser().resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError(f"path is outside TMD MCP root: {path}")
        if resolved.suffix != ".tmd":
            raise ValueError(f"path must be a .tmd file: {path}")
        return resolved

    def _normalize_result(self, result: Any) -> Any:
        if isinstance(result, list):
            return [self._row_to_dict(item) for item in result]
        return result

    @staticmethod
    def _row_to_dict(item: Any) -> Any:
        if hasattr(item, "fields"):
            return {"_id": item.id, "_table": item.table, **item.fields}
        return item

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, indent=2, default=str)

    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "tmd_list_files",
                "description": "List .tmd files under the configured root.",
                "inputSchema": {"type": "object", "properties": {"pattern": {"type": "string"}, "max_files": {"type": "integer"}}},
            },
            {
                "name": "tmd_parse_file",
                "description": "Parse a TMD file and return schema plus rows.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "include_rows": {"type": "boolean"}, "max_rows": {"type": "integer"}}, "required": ["path"]},
            },
            {
                "name": "tmd_query_file",
                "description": "Run a TMD query against one file.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "query_text": {"type": "string"}}, "required": ["path", "query_text"]},
            },
            {
                "name": "tmd_get_row",
                "description": "Fetch one row by row id.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "row_id": {"type": ["string", "integer"]}}, "required": ["path", "row_id"]},
            },
            {
                "name": "tmd_append_row",
                "description": "Append one row to a TMD file. Writes to disk.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "fields": {"type": "object"}, "row_id": {"type": ["string", "integer", "null"]}, "table": {"type": ["string", "null"]}}, "required": ["path", "fields"]},
            },
            {
                "name": "tmd_update_row",
                "description": "Update fields on an existing row. Writes to disk.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "row_id": {"type": ["string", "integer"]}, "fields": {"type": "object"}, "replace": {"type": "boolean"}}, "required": ["path", "row_id", "fields"]},
            },
            {
                "name": "tmd_validate_file",
                "description": "Validate a TMD file and return errors/warnings.",
                "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            },
        ]

    @staticmethod
    def _result_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
