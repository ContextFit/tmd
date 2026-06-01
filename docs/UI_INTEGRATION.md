# TMD UI Integration Guide

Status: draft 0.1

This guide is for AI-native UI agents and applications that want to render, edit, and round-trip TMD files.

## Integration Principle

TMD is structured table source with row-safe operations.

The UI should treat rows, row IDs, schema, computed fields, references, and prose sections as canonical data. Spreadsheet-like grids, filters, charts, and cards are render outputs or view state.

## Recommended First Path

1. Read TMD through the reference CLI:

```bash
tmd export path/to/file.tmd --format json
```

2. Render from the exported JSON object model.
3. Use row-safe operations for edits:

```bash
tmd rows path/to/file.tmd --json
tmd row path/to/file.tmd ROW_ID --json
tmd append-row path/to/file.tmd --set name=Northwind --set amount=500 --json
tmd update-row path/to/file.tmd ROW_ID --set paid=true --json
```

4. Validate before save:

```bash
tmd validate path/to/file.tmd --json
```

## Object Model

The JSON export has these top-level fields:

- `meta`: table metadata
- `data[]`: rows

`meta` includes:

- `title`
- `table`
- `schema`

Each row includes:

- `_id`
- one property per field

Reference values are represented as objects:

```json
{ "_ref": "companies/acme" }
```

## UI Surfaces

For a first TMD implementation, build these surfaces:

- table/grid view
- row detail inspector
- schema panel
- computed fields panel
- reference/source panel
- validation panel
- row operation controls
- raw TMD source pane or revealable editor

## Required Behaviors

- Preserve row IDs unless the user explicitly renames a row.
- Use append/update row operations for normal edits.
- Treat schema as canonical field guidance, not optional decoration.
- Preserve reference objects and wiki-style refs.
- Keep UI-only sort/filter/group state outside TMD unless explicitly saved as a view elsewhere.
- Validate before save or sync.

## Edit Operations

Recommended primitive operations:

- list rows
- get row
- append row
- update row
- validate table
- export JSON
- export CSV/JSONL
- inspect schema
- follow reference

For destructive operations such as delete/rename, the UI should show affected references and require explicit confirmation.

## ContextFit Integration

A ContextFit ingestion path should chunk TMD by:

- whole table for small tables
- schema plus row groups for larger tables
- individual rows for precise lookup
- prose sections as normal markdown context

Recommended metadata:

- `tmd_kind`
- `tmd_table`
- `tmd_row_id`
- `tmd_fields`
- `tmd_schema_fields`
- `tmd_refs`
- `line`

This supports table lookup, row-level provenance, structured filters, and reference traversal.
