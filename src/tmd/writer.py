"""
TMD Writer: Write TMD documents.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from tmd.parser import TMDDocument, Row, Schema


def write(doc: TMDDocument) -> str:
    """Write a TMDDocument to string."""
    lines = []
    
    # Front matter
    if doc.front_matter or doc.schema.fields or doc.schema.computed:
        lines.append('---')
        
        front_matter = dict(doc.front_matter)
        
        # Add schema if present
        if doc.schema.fields:
            schema_dict = {}
            for name, info in doc.schema.fields.items():
                type_str = info.get("type", "text")
                
                if info.get("pk"):
                    type_str += " (pk)"
                if info.get("nullable"):
                    type_str += "?"
                if info.get("default"):
                    type_str += f" = {info['default']}"
                if info.get("ref_table"):
                    type_str = f"ref({info['ref_table']})"
                
                schema_dict[name] = type_str
            
            front_matter["schema"] = schema_dict
        
        if doc.schema.computed:
            front_matter["computed"] = doc.schema.computed
        
        yaml_str = yaml.dump(front_matter, default_flow_style=False, sort_keys=False)
        lines.append(yaml_str.rstrip())
        lines.append('---')
        lines.append('')
    
    # Title
    if doc.title:
        lines.append(f'# {doc.title}')
        lines.append('')
    
    # Rows
    table_name = doc.table_name or "data"
    for row in doc.rows:
        row_str = _format_row(row, table_name)
        lines.append(row_str)
    
    # Prose
    if doc.prose:
        lines.append('')
        lines.append(doc.prose)
    
    return '\n'.join(lines)


def _format_row(row: Row, default_table: str) -> str:
    """Format a single row."""
    table = row.table or default_table
    row_id = row.id if row.id is not None else ""
    
    fields_parts = []
    multiline_parts = []
    
    for key, value in row.fields.items():
        formatted = _format_value(value)
        
        # Check if multiline needed
        if isinstance(value, str) and '\n' in value:
            multiline_parts.append((key, value))
        else:
            fields_parts.append(f"{key}={formatted}")
    
    row_str = f"{table}[{row_id}]: {', '.join(fields_parts)}"
    
    # Add multiline fields
    for key, value in multiline_parts:
        row_str += f"\n  {key}: |\n"
        for line in value.split('\n'):
            row_str += f"    {line}\n"
    
    return row_str.rstrip()


def _format_value(value: Any) -> str:
    """Format a value for output."""
    if value is None:
        return "null"
    
    if isinstance(value, bool):
        return "true" if value else "false"
    
    if isinstance(value, (int, float)):
        return str(value)
    
    if isinstance(value, dict) and "_ref" in value:
        return f"[[{value['_ref']}]]"
    
    if isinstance(value, list):
        items = [_format_value(v) for v in value]
        return f"[{', '.join(items)}]"
    
    # String - check if quoting needed
    value = str(value)
    needs_quotes = (
        ',' in value or
        '=' in value or
        value.startswith(' ') or
        value.endswith(' ') or
        '"' in value
    )
    
    if needs_quotes:
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    
    return value


def write_file(doc: TMDDocument, path: str | Path) -> None:
    """Write a TMDDocument to a file."""
    path = Path(path)
    content = write(doc)
    path.write_text(content)


def from_dicts(
    data: list[dict],
    table_name: str = "data",
    title: str | None = None,
    schema: dict[str, str] | None = None,
    computed: dict[str, str] | None = None,
) -> TMDDocument:
    """
    Create a TMDDocument from a list of dicts.
    
    Args:
        data: List of row dicts
        table_name: Name for the table
        title: Document title (defaults to table_name.title())
        schema: Optional schema dict {field: type}
        computed: Optional computed fields dict {name: formula}
    """
    doc = TMDDocument()
    doc.title = title or table_name.replace('_', ' ').title()
    doc.table_name = table_name
    
    # Build schema
    if schema:
        doc.schema = Schema.from_dict({"schema": schema})
    if computed:
        doc.schema.computed = computed
    
    # Add rows
    for i, row_data in enumerate(data):
        row_id = row_data.pop('_id', row_data.pop('id', i + 1))
        row = Row(
            table=table_name,
            id=row_id,
            fields=row_data,
            line_number=i + 1
        )
        doc.rows.append(row)
    
    return doc
