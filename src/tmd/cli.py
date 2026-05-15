#!/usr/bin/env python3
"""
TMD CLI: Command-line interface for Tabular Markdown.

Usage:
    tmd parse invoices.tmd
    tmd query invoices.tmd "SUM(amount WHERE paid=false)"
    tmd validate invoices.tmd
    tmd fmt invoices.tmd
    tmd export invoices.tmd --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tmd.parser import parse_file
from tmd.query import query, compute
from tmd.writer import write
from tmd.ops import (
    append_row,
    get_row,
    list_rows,
    parse_field_assignments,
    update_row,
    validate_file,
)


def cmd_parse(args):
    """Parse and dump a TMD file."""
    doc = parse_file(args.file)
    
    output = {
        "title": doc.title,
        "table_name": doc.table_name,
        "row_count": len(doc.rows),
        "schema": {
            "fields": doc.schema.fields,
            "computed": doc.schema.computed,
        },
        "rows": doc.to_dicts(),
    }
    
    if args.json:
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"Title: {doc.title}")
        print(f"Table: {doc.table_name}")
        print(f"Rows: {len(doc.rows)}")
        print(f"Schema: {list(doc.schema.fields.keys())}")
        print(f"Computed: {list(doc.schema.computed.keys())}")
        print()
        for row in doc.rows[:5]:
            print(f"  [{row.id}] {dict(row.fields)}")
        if len(doc.rows) > 5:
            print(f"  ... and {len(doc.rows) - 5} more rows")


def cmd_query(args):
    """Query a TMD file."""
    doc = parse_file(args.file)
    result = query(doc, args.query)
    
    if args.json:
        if isinstance(result, list):
            output = [{"_id": r.id, **r.fields} if hasattr(r, 'fields') else r for r in result]
        else:
            output = result
        print(json.dumps(output, indent=2, default=str))
    else:
        if isinstance(result, list):
            for r in result:
                if hasattr(r, 'fields'):
                    print(f"[{r.id}] {dict(r.fields)}")
                else:
                    print(r)
            print(f"\n{len(result)} row(s)")
        else:
            print(result)


def cmd_compute(args):
    """Compute all computed fields."""
    doc = parse_file(args.file)
    results = compute(doc)
    
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for name, value in results.items():
            print(f"{name}: {value}")


def cmd_validate(args):
    """Validate a TMD file."""
    try:
        result = validate_file(args.file)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        elif result["ok"]:
            print(f"✅ {args.file}: Valid ({result['row_count']} rows)")
        else:
            print(f"❌ {args.file}: {len(result['errors'])} error(s)")
            for error in result["errors"]:
                print(f"  - {error}")
        if not result["ok"]:
            sys.exit(1)
    except Exception as e:
        if args.json:
            print(json.dumps({"ok": False, "path": args.file, "errors": [str(e)], "warnings": []}, indent=2))
        else:
            print(f"❌ {args.file}: Parse error - {e}")
        sys.exit(1)


def cmd_fmt(args):
    """Format/prettify a TMD file."""
    doc = parse_file(args.file)
    formatted = write(doc)
    
    if args.write:
        Path(args.file).write_text(formatted)
        print(f"Formatted {args.file}")
    else:
        print(formatted)


def cmd_import(args):
    """Import data from CSV or JSON to TMD."""
    from tmd.writer import from_dicts, write_file
    
    input_path = Path(args.input)
    
    if args.format == 'csv' or (not args.format and input_path.suffix == '.csv'):
        import csv
        with open(input_path) as f:
            reader = csv.DictReader(f)
            data = list(reader)
            # Convert numeric strings
            for row in data:
                for k, v in row.items():
                    if v:
                        try:
                            if '.' in v:
                                row[k] = float(v)
                            else:
                                row[k] = int(v)
                        except ValueError:
                            if v.lower() in ('true', 'false'):
                                row[k] = v.lower() == 'true'
    
    elif args.format == 'json' or (not args.format and input_path.suffix == '.json'):
        data = json.loads(input_path.read_text())
        if isinstance(data, dict) and 'data' in data:
            data = data['data']  # Handle {meta: ..., data: [...]}
    
    elif args.format == 'jsonl' or (not args.format and input_path.suffix == '.jsonl'):
        data = []
        with open(input_path) as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
    else:
        print(f"Unknown format. Use --format csv|json|jsonl")
        sys.exit(1)
    
    # Create document
    table_name = args.table or input_path.stem.lower().replace('-', '_').replace(' ', '_')
    doc = from_dicts(data, table_name=table_name)
    
    # Output
    output_path = args.output or input_path.with_suffix('.tmd')
    write_file(doc, output_path)
    print(f"Imported {len(data)} rows to {output_path}")


def cmd_export(args):
    """Export TMD to another format."""
    doc = parse_file(args.file)
    
    if args.format == 'json':
        output = {
            "meta": {
                "title": doc.title,
                "table": doc.table_name,
                "schema": doc.schema.fields,
            },
            "data": doc.to_dicts(),
        }
        print(json.dumps(output, indent=2, default=str))
    
    elif args.format == 'jsonl':
        for row in doc.rows:
            print(json.dumps({"_id": row.id, **row.fields}, default=str))
    
    elif args.format == 'csv':
        import csv
        import sys
        
        if not doc.rows:
            return
        
        fieldnames = ['_id'] + list(doc.rows[0].fields.keys())
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in doc.rows:
            row_dict = {"_id": row.id, **row.fields}
            # Flatten complex values
            for k, v in row_dict.items():
                if isinstance(v, (dict, list)):
                    row_dict[k] = json.dumps(v)
            writer.writerow(row_dict)


def cmd_rows(args):
    """List rows in a TMD file."""
    rows = list_rows(args.file)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        for row in rows:
            row_id = row.pop("_id")
            row.pop("_line_number", None)
            table = row.pop("_table", None)
            prefix = f"{table}[{row_id}]" if table else f"[{row_id}]"
            print(f"{prefix}: {row}")
        print(f"\n{len(rows)} row(s)")


def cmd_row(args):
    """Fetch one row by id."""
    row = get_row(args.file, args.row_id)
    if args.json:
        print(json.dumps(row, indent=2, default=str))
    else:
        row_id = row.pop("_id")
        row.pop("_line_number", None)
        table = row.pop("_table", None)
        prefix = f"{table}[{row_id}]" if table else f"[{row_id}]"
        print(f"{prefix}: {row}")


def cmd_append_row(args):
    """Append one row to a TMD file."""
    fields = parse_field_assignments(args.set)
    row = append_row(args.file, fields=fields, row_id=args.id, table=args.table)
    if args.json:
        print(json.dumps(row, indent=2, default=str))
    else:
        print(f"Appended row [{row['_id']}] to {args.file}")


def cmd_update_row(args):
    """Update one row in a TMD file."""
    fields = parse_field_assignments(args.set)
    row = update_row(args.file, row_id=args.row_id, fields=fields, replace=args.replace)
    if args.json:
        print(json.dumps(row, indent=2, default=str))
    else:
        print(f"Updated row [{row['_id']}] in {args.file}")


def cmd_mcp(args):
    """Run the TMD MCP stdio server."""
    from tmd.mcp import MCPServerConfig, TMDMCPServer

    server = TMDMCPServer(
        MCPServerConfig(
            root=Path(args.root).expanduser().resolve(),
            max_files=args.max_files,
            max_rows=args.max_rows,
        )
    )
    server.serve()


def main():
    parser = argparse.ArgumentParser(
        description="TMD: Tabular Markdown CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # parse
    p = subparsers.add_parser('parse', help='Parse and inspect a TMD file')
    p.add_argument('file', help='TMD file to parse')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_parse)
    
    # query
    p = subparsers.add_parser('query', help='Query a TMD file')
    p.add_argument('file', help='TMD file to query')
    p.add_argument('query', help='Query string')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_query)
    
    # compute
    p = subparsers.add_parser('compute', help='Compute all computed fields')
    p.add_argument('file', help='TMD file')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_compute)
    
    # validate
    p = subparsers.add_parser('validate', help='Validate a TMD file')
    p.add_argument('file', help='TMD file to validate')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_validate)
    
    # fmt
    p = subparsers.add_parser('fmt', help='Format a TMD file')
    p.add_argument('file', help='TMD file to format')
    p.add_argument('-w', '--write', action='store_true', help='Write back to file')
    p.set_defaults(func=cmd_fmt)
    
    # export
    p = subparsers.add_parser('export', help='Export to another format')
    p.add_argument('file', help='TMD file to export')
    p.add_argument('--format', '-f', choices=['json', 'jsonl', 'csv'], 
                   default='json', help='Output format')
    p.set_defaults(func=cmd_export)
    

    # rows
    p = subparsers.add_parser('rows', help='List rows in a TMD file')
    p.add_argument('file', help='TMD file')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_rows)

    # row
    p = subparsers.add_parser('row', help='Fetch one row by id')
    p.add_argument('file', help='TMD file')
    p.add_argument('row_id', help='Row id')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_row)

    # append-row
    p = subparsers.add_parser('append-row', help='Append one row to a TMD file')
    p.add_argument('file', help='TMD file')
    p.add_argument('--id', help='Row id (default: next numeric id)')
    p.add_argument('--table', help='Table name override')
    p.add_argument('--set', action='append', required=True, help='Field assignment key=value; repeat for multiple fields')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_append_row)

    # update-row
    p = subparsers.add_parser('update-row', help='Update one row in a TMD file')
    p.add_argument('file', help='TMD file')
    p.add_argument('row_id', help='Row id')
    p.add_argument('--set', action='append', required=True, help='Field assignment key=value; repeat for multiple fields')
    p.add_argument('--replace', action='store_true', help='Replace all fields instead of merging')
    p.add_argument('--json', action='store_true', help='Output as JSON')
    p.set_defaults(func=cmd_update_row)

    # mcp
    p = subparsers.add_parser('mcp', help='Run a TMD MCP stdio server')
    p.add_argument('--root', default='.', help='Filesystem root for allowed .tmd files')
    p.add_argument('--max-files', type=int, default=200, help='Maximum files returned by list tool')
    p.add_argument('--max-rows', type=int, default=100, help='Maximum rows returned by parse tool')
    p.set_defaults(func=cmd_mcp)

    # import
    p = subparsers.add_parser('import', help='Import from CSV, JSON, or JSONL')
    p.add_argument('input', help='Input file (CSV, JSON, or JSONL)')
    p.add_argument('-o', '--output', help='Output TMD file (default: input.tmd)')
    p.add_argument('-t', '--table', help='Table name (default: filename)')
    p.add_argument('--format', '-f', choices=['csv', 'json', 'jsonl'],
                   help='Input format (auto-detected from extension)')
    p.set_defaults(func=cmd_import)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
