# TMD: Tabular Markdown

**Agent-native structured data format**

TMD is a markdown-based format for storing structured, tabular data that is:
- **Human-readable** — Edit in any text editor
- **Git-friendly** — Clean diffs, easy merges
- **Token-efficient** — Optimized for LLM context
- **Agent-native** — Live queries, cross-file references

## Quick Example

```markdown
---
schema:
  id: int (pk)
  name: text
  amount: decimal
  paid: bool
computed:
  total: SUM(amount)
  outstanding: SUM(amount WHERE paid=false)
---

# Invoices

invoices[1]: name=Acme Corp, amount=1500.00, paid=false
invoices[2]: name=Widget Inc, amount=750.50, paid=true

## Notes
Follow up with [[contacts/john-smith]] about payment.
```

## Installation

```bash
pip install -e .
```

## CLI Usage

```bash
# Parse and inspect
tmd parse invoices.tmd

# Query data
tmd query invoices.tmd "SUM(amount WHERE paid=false)"
tmd query invoices.tmd "WHERE paid=false"

# Compute all formulas
tmd compute invoices.tmd

# Validate
tmd validate invoices.tmd

# Row-safe agent operations
tmd rows invoices.tmd --json
tmd row invoices.tmd 1 --json
tmd append-row invoices.tmd --set name=Northwind --set amount=500 --set paid=false --json
tmd update-row invoices.tmd 1 --set paid=true --json

# Export
tmd export invoices.tmd --format json
tmd export invoices.tmd --format csv
```

## MCP for Claude Desktop / local agents

TMD includes a dependency-free MCP stdio server for row-aware structured data tools. Point it at a folder that contains `.tmd` files:

```bash
tmd mcp --root ~/Documents/project-orion
```

Claude Desktop config example:

```json
{
  "mcpServers": {
    "tmd": {
      "command": "tmd",
      "args": ["mcp", "--root", "/Users/YOU/Documents/project-orion"]
    }
  }
}
```

Available MCP tools:

- `tmd_list_files` — list `.tmd` files under the configured root
- `tmd_parse_file` — parse schema and rows
- `tmd_query_file` — run TMD queries like `SUM(amount WHERE paid=false)`
- `tmd_get_row` — fetch one row by id
- `tmd_append_row` — append a row safely
- `tmd_update_row` — update fields on an existing row
- `tmd_validate_file` — return validation errors/warnings

TMD files do not need separate vaults. They can live inside existing ContextFit vaults for search/retrieval, while TMD CLI/MCP handles row-aware reads and writes.

## Integration Docs

- [UI integration guide](docs/UI_INTEGRATION.md)
- [JSON contract](docs/JSON_CONTRACT.md)
- [Edit operations](docs/EDIT_OPERATIONS.md)
- [JSON schema](schema/tmd.schema.json)

## Python API

```python
from tmd import parse_file, query, compute, append_row, update_row

# Load document
doc = parse_file("invoices.tmd")

# Access rows
for row in doc:
    print(row.id, row["name"], row["amount"])

# Filter
unpaid = doc.filter(paid=False)

# Query
total = query(doc, "SUM(amount)")
unpaid_rows = query(doc, "WHERE paid=false")

# Compute all formulas
results = compute(doc)
print(results["outstanding"])

# Row-safe writes
append_row("invoices.tmd", {"name": "Northwind", "amount": 500, "paid": False})
update_row("invoices.tmd", 1, {"paid": True})
```

## Format Features

- **Schema with types**: `int`, `decimal`, `text`, `bool`, `date`, `datetime`
- **References**: Wiki-style links `[[path/to/file]]`
- **Computed fields**: `SUM()`, `AVG()`, `COUNT()`, `MIN()`, `MAX()`
- **Filters**: `WHERE field=value AND field2>10`
- **Multiline text**: YAML-style blocks for long content
- **Prose sections**: Mix data with documentation

See [SPEC.md](SPEC.md) for full specification.

## License

MIT
