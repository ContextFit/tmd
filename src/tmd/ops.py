"""Row-safe operations for TMD files.

These helpers back both the CLI and MCP server. They intentionally operate at the
TMD document level and rewrite the file through the canonical writer so agent
writes stay parseable and diff-friendly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tmd.parser import Row, TMDDocument, parse_file, _parse_value
from tmd.writer import write_file


def row_to_dict(row: Row) -> dict[str, Any]:
    """Convert a row to an agent-friendly dictionary."""
    return {
        "_id": row.id,
        "_table": row.table,
        "_line_number": row.line_number,
        **row.fields,
    }


def parse_field_assignments(assignments: list[str]) -> dict[str, Any]:
    """Parse CLI field assignments like ``name=Acme`` into typed values."""
    fields: dict[str, Any] = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(f"field assignment must be key=value: {assignment}")
        key, value = assignment.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"field assignment has empty key: {assignment}")
        fields[key] = _parse_value(value.strip())
    return fields


def find_row(doc: TMDDocument, row_id: str | int) -> Row:
    """Find a row by id using string-compatible matching."""
    for row in doc.rows:
        if str(row.id) == str(row_id):
            return row
    raise KeyError(f"row id not found: {row_id}")


def list_rows(path: str | Path) -> list[dict[str, Any]]:
    doc = parse_file(path)
    return [row_to_dict(row) for row in doc.rows]


def get_row(path: str | Path, row_id: str | int) -> dict[str, Any]:
    doc = parse_file(path)
    return row_to_dict(find_row(doc, row_id))


def append_row(
    path: str | Path,
    fields: dict[str, Any],
    row_id: str | int | None = None,
    table: str | None = None,
) -> dict[str, Any]:
    """Append a row to a TMD file and return the appended row."""
    path = Path(path)
    doc = parse_file(path)
    if row_id is None:
        row_id = _next_row_id(doc)
    else:
        try:
            find_row(doc, row_id)
        except KeyError:
            pass
        else:
            raise ValueError(f"row id already exists: {row_id}")

    row = Row(
        table=table or doc.table_name or (doc.rows[0].table if doc.rows else path.stem),
        id=row_id,
        fields=dict(fields),
        line_number=0,
    )
    doc.rows.append(row)
    write_file(doc, path)
    return row_to_dict(row)


def update_row(
    path: str | Path,
    row_id: str | int,
    fields: dict[str, Any],
    replace: bool = False,
) -> dict[str, Any]:
    """Update a row in-place and return the updated row."""
    path = Path(path)
    doc = parse_file(path)
    row = find_row(doc, row_id)
    if replace:
        row.fields = dict(fields)
    else:
        row.fields.update(fields)
    write_file(doc, path)
    return row_to_dict(row)


def validate_document(doc: TMDDocument) -> dict[str, Any]:
    """Return validation results without printing or exiting."""
    errors: list[str] = []
    warnings: list[str] = []

    if doc.schema.fields:
        required = [
            key
            for key, info in doc.schema.fields.items()
            if not info.get("nullable") and not info.get("default") and not info.get("pk")
        ]
        for row in doc.rows:
            for field in required:
                if field not in row.fields or row.fields[field] is None:
                    errors.append(f"Row [{row.id}]: Missing required field '{field}'")

    seen: set[str] = set()
    for row in doc.rows:
        row_id = str(row.id)
        if row_id in seen:
            errors.append(f"Duplicate row ID: {row.id}")
        seen.add(row_id)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "row_count": len(doc.rows),
    }


def validate_file(path: str | Path) -> dict[str, Any]:
    doc = parse_file(path)
    result = validate_document(doc)
    result["path"] = str(path)
    return result


def _next_row_id(doc: TMDDocument) -> int:
    numeric_ids = [row.id for row in doc.rows if isinstance(row.id, int)]
    return (max(numeric_ids) + 1) if numeric_ids else (len(doc.rows) + 1)
