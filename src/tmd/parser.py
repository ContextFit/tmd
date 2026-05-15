"""
TMD Parser: Parse Tabular Markdown files.
"""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Schema:
    """Table schema definition."""
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    computed: dict[str, str] = field(default_factory=dict)
    primary_key: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> Schema:
        schema = cls()
        
        # Parse field definitions
        for name, type_def in data.get("schema", {}).items():
            field_info = cls._parse_field_type(type_def)
            schema.fields[name] = field_info
            if field_info.get("pk"):
                schema.primary_key = name
        
        # Parse computed fields
        schema.computed = data.get("computed", {})
        
        return schema
    
    @staticmethod
    def _parse_field_type(type_def: str) -> dict[str, Any]:
        """Parse type definition like 'int (pk)' or 'text?' or 'ref(companies)'."""
        info: dict[str, Any] = {"type": "text", "nullable": False, "pk": False}
        
        if not isinstance(type_def, str):
            return info
        
        type_def = type_def.strip()
        
        # Check for primary key
        if "(pk)" in type_def:
            info["pk"] = True
            type_def = type_def.replace("(pk)", "").strip()
        
        # Check for nullable
        if type_def.endswith("?"):
            info["nullable"] = True
            type_def = type_def[:-1].strip()
        
        # Check for default value
        if "=" in type_def:
            type_def, default = type_def.split("=", 1)
            info["default"] = default.strip()
            type_def = type_def.strip()
        
        # Check for ref
        ref_match = re.match(r"ref\((\w+)\)", type_def)
        if ref_match:
            info["type"] = "ref"
            info["ref_table"] = ref_match.group(1)
        # Check for list
        elif type_def.startswith("list("):
            info["type"] = "list"
            inner = type_def[5:-1]
            info["inner_type"] = inner
        # Check for enum
        elif type_def.startswith("enum("):
            info["type"] = "enum"
            values = type_def[5:-1].split(",")
            info["enum_values"] = [v.strip() for v in values]
        else:
            info["type"] = type_def if type_def else "text"
        
        return info


@dataclass
class Row:
    """A single data row."""
    table: str
    id: str | int | None
    fields: dict[str, Any]
    line_number: int = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        return self.fields[key]
    
    def keys(self):
        return self.fields.keys()
    
    def values(self):
        return self.fields.values()
    
    def items(self):
        return self.fields.items()


@dataclass  
class TMDDocument:
    """A parsed TMD document."""
    path: Path | None = None
    title: str | None = None
    table_name: str | None = None
    schema: Schema = field(default_factory=Schema)
    rows: list[Row] = field(default_factory=list)
    prose: str = ""
    front_matter: dict[str, Any] = field(default_factory=dict)
    
    def __len__(self) -> int:
        return len(self.rows)
    
    def __iter__(self):
        return iter(self.rows)
    
    def __getitem__(self, key: str | int) -> Row | list[Row]:
        if isinstance(key, int):
            return self.rows[key]
        # Find by ID
        for row in self.rows:
            if str(row.id) == str(key):
                return row
        raise KeyError(f"Row with id '{key}' not found")
    
    def filter(self, **kwargs) -> list[Row]:
        """Filter rows by field values."""
        results = []
        for row in self.rows:
            match = True
            for k, v in kwargs.items():
                if row.get(k) != v:
                    match = False
                    break
            if match:
                results.append(row)
        return results
    
    def to_dicts(self) -> list[dict]:
        """Convert rows to list of dicts."""
        return [{"_id": r.id, **r.fields} for r in self.rows]


# Row parsing regex
ROW_PATTERN = re.compile(
    r'^(\w+)\[([^\]]*)\]:\s*(.+)$'
)


def parse(content: str, path: Path | None = None) -> TMDDocument:
    """Parse TMD content string."""
    doc = TMDDocument(path=path)
    lines = content.split('\n')
    
    # Parse front matter
    if lines and lines[0].strip() == '---':
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_idx = i
                break
        
        if end_idx:
            yaml_content = '\n'.join(lines[1:end_idx])
            try:
                doc.front_matter = yaml.safe_load(yaml_content) or {}
                doc.schema = Schema.from_dict(doc.front_matter)
            except yaml.YAMLError:
                pass
            lines = lines[end_idx + 1:]
    
    prose_lines = []
    in_multiline = False
    multiline_field = None
    multiline_value = []
    current_row = None
    
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Handle multiline values
        if in_multiline:
            if line.startswith('  ') or line.startswith('\t'):
                # Continue multiline
                if line.strip() == '|':
                    continue  # Skip the | marker
                multiline_value.append(line.strip())
                continue
            else:
                # End multiline
                if current_row and multiline_field:
                    current_row.fields[multiline_field] = '\n'.join(multiline_value)
                in_multiline = False
                multiline_field = None
                multiline_value = []
        
        # Parse H1 as title/table name
        if stripped.startswith('# '):
            doc.title = stripped[2:].strip()
            doc.table_name = doc.title.lower().replace(' ', '_')
            continue
        
        # Try to parse as data row
        row_match = ROW_PATTERN.match(stripped)
        if row_match:
            table, row_id, fields_str = row_match.groups()
            
            # Parse row ID
            if row_id == '':
                parsed_id = len(doc.rows) + 1
            elif row_id.isdigit():
                parsed_id = int(row_id)
            else:
                parsed_id = row_id
            
            # Parse fields
            fields = _parse_fields(fields_str)
            
            row = Row(
                table=table,
                id=parsed_id,
                fields=fields,
                line_number=line_num
            )
            doc.rows.append(row)
            current_row = row
            
            # Check for multiline start
            if fields_str.rstrip().endswith(':'):
                # Field with multiline value coming
                last_field = list(fields.keys())[-1] if fields else None
                if last_field and fields[last_field] == '':
                    in_multiline = True
                    multiline_field = last_field
                    multiline_value = []
            continue
        
        # Check for multiline field continuation (indented field: |)
        if stripped.endswith(': |') and current_row:
            field_name = stripped[:-3].strip()
            in_multiline = True
            multiline_field = field_name
            multiline_value = []
            continue
        
        # Collect prose
        if stripped and not stripped.startswith('#'):
            prose_lines.append(line)
    
    doc.prose = '\n'.join(prose_lines).strip()
    
    return doc


def _parse_fields(fields_str: str) -> dict[str, Any]:
    """Parse field=value pairs from a row."""
    fields = {}
    
    # State machine for parsing
    current_key = ""
    current_value = ""
    in_quotes = False
    in_brackets = False
    bracket_depth = 0
    
    i = 0
    while i < len(fields_str):
        char = fields_str[i]
        
        if char == '"' and (i == 0 or fields_str[i-1] != '\\'):
            in_quotes = not in_quotes
            current_value += char
        elif char == '[' and not in_quotes:
            in_brackets = True
            bracket_depth += 1
            current_value += char
        elif char == ']' and not in_quotes:
            bracket_depth -= 1
            if bracket_depth == 0:
                in_brackets = False
            current_value += char
        elif char == '=' and not in_quotes and not in_brackets and not current_key:
            current_key = current_value.strip()
            current_value = ""
        elif char == ',' and not in_quotes and not in_brackets:
            # End of field
            if current_key:
                fields[current_key] = _parse_value(current_value.strip())
            current_key = ""
            current_value = ""
        else:
            current_value += char
        
        i += 1
    
    # Don't forget the last field
    if current_key:
        fields[current_key] = _parse_value(current_value.strip())
    
    return fields


def _parse_value(value: str) -> Any:
    """Parse a value string into appropriate Python type."""
    if not value:
        return ""
    
    # Remove quotes
    if value.startswith('"') and value.endswith('"'):
        # Unescape
        return value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    
    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    
    # Null
    if value.lower() == 'null':
        return None
    
    # Wiki link (reference)
    if value.startswith('[[') and value.endswith(']]'):
        return {"_ref": value[2:-2]}
    
    # List
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1]
        items = [_parse_value(v.strip()) for v in inner.split(',')]
        return items
    
    # Number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    
    return value


def parse_file(path: str | Path) -> TMDDocument:
    """Parse a TMD file."""
    path = Path(path)
    content = path.read_text()
    return parse(content, path=path)
