"""
TMD Query: Query and compute on TMD documents.
"""

from __future__ import annotations

import re
import operator
from typing import Any, Callable
from pathlib import Path

from tmd.parser import TMDDocument, Row, parse_file


# Comparison operators
OPS: dict[str, Callable[[Any, Any], bool]] = {
    '=': operator.eq,
    '==': operator.eq,
    '!=': operator.ne,
    '<>': operator.ne,
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
}


def query(doc: TMDDocument, query_str: str) -> list[Row] | Any:
    """
    Execute a query on a TMD document.
    
    Supports:
    - SELECT * WHERE field=value
    - SELECT field1, field2 WHERE condition
    - SUM(field), AVG(field), COUNT(), MIN(field), MAX(field)
    - Filters: WHERE field=value AND field2>10
    """
    query_str = query_str.strip()
    
    # Handle COUNT(WHERE ...) - no field, just condition
    count_where_match = re.match(
        r'^COUNT\(\s*WHERE\s+(.+)\)$',
        query_str, re.IGNORECASE
    )
    if count_where_match:
        where = count_where_match.group(1)
        return _compute_aggregate(doc, 'COUNT', None, where)
    
    # Aggregate functions - handle WHERE inside or outside parentheses
    # Pattern: FUNC(field) WHERE cond OR FUNC(field WHERE cond)
    agg_match = re.match(
        r'^(SUM|AVG|COUNT|MIN|MAX)\(([^)]*?)(?:\s+WHERE\s+([^)]+))?\)(?:\s+WHERE\s+(.+))?$', 
        query_str, re.IGNORECASE
    )
    if agg_match:
        func, field, inner_where, outer_where = agg_match.groups()
        where = inner_where or outer_where
        return _compute_aggregate(doc, func.upper(), field.strip() if field else None, where)
    
    # Try alternate pattern for WHERE outside
    agg_match = re.match(
        r'^(SUM|AVG|COUNT|MIN|MAX)\(([^)]*)\)\s+WHERE\s+(.+)$', 
        query_str, re.IGNORECASE
    )
    if agg_match:
        func, field, where = agg_match.groups()
        return _compute_aggregate(doc, func.upper(), field, where)
    
    # SELECT queries
    select_match = re.match(r'^SELECT\s+(.+?)\s+(?:FROM\s+\w+\s+)?WHERE\s+(.+)$', 
                           query_str, re.IGNORECASE)
    if select_match:
        fields_str, where = select_match.groups()
        rows = _filter_rows(doc.rows, where)
        
        if fields_str.strip() == '*':
            return rows
        
        # Project specific fields
        fields = [f.strip() for f in fields_str.split(',')]
        return [{f: r.get(f) for f in fields} for r in rows]
    
    # Simple SELECT * WHERE
    where_match = re.match(r'^(?:SELECT\s+\*\s+)?WHERE\s+(.+)$', query_str, re.IGNORECASE)
    if where_match:
        where = where_match.group(1)
        return _filter_rows(doc.rows, where)
    
    # Just a field list (implicit SELECT *)
    if '=' in query_str or '<' in query_str or '>' in query_str:
        return _filter_rows(doc.rows, query_str)
    
    raise ValueError(f"Could not parse query: {query_str}")


def _filter_rows(rows: list[Row], where: str | None) -> list[Row]:
    """Filter rows by WHERE clause."""
    if not where:
        return rows
    
    # Parse conditions (simple AND-only for now)
    conditions = re.split(r'\s+AND\s+', where, flags=re.IGNORECASE)
    
    results = []
    for row in rows:
        if _matches_conditions(row, conditions):
            results.append(row)
    
    return results


def _matches_conditions(row: Row, conditions: list[str]) -> bool:
    """Check if row matches all conditions."""
    for cond in conditions:
        if not _matches_condition(row, cond.strip()):
            return False
    return True


def _matches_condition(row: Row, condition: str) -> bool:
    """Check if row matches a single condition."""
    # Find operator
    for op_str in ['<=', '>=', '<>', '!=', '==', '=', '<', '>']:
        if op_str in condition:
            parts = condition.split(op_str, 1)
            if len(parts) == 2:
                field = parts[0].strip()
                value_str = parts[1].strip()
                
                row_value = row.get(field)
                compare_value = _parse_condition_value(value_str)
                
                op_func = OPS.get(op_str)
                if op_func:
                    try:
                        return op_func(row_value, compare_value)
                    except TypeError:
                        return False
    
    return False


def _parse_condition_value(value: str) -> Any:
    """Parse a value from a condition."""
    value = value.strip()
    
    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    
    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    
    # Null
    if value.lower() == 'null':
        return None
    
    # Reference
    if value.startswith('[[') and value.endswith(']]'):
        return {"_ref": value[2:-2]}
    
    # Number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    
    return value


def _compute_aggregate(doc: TMDDocument, func: str, field: str | None, where: str | None) -> Any:
    """Compute an aggregate function."""
    rows = _filter_rows(doc.rows, where)
    
    if func == 'COUNT':
        return len(rows)
    
    if not field:
        raise ValueError(f"{func} requires a field argument")
    
    field = field.strip()
    values = []
    for row in rows:
        val = row.get(field)
        if val is not None and isinstance(val, (int, float)):
            values.append(val)
    
    if not values:
        return 0 if func == 'SUM' else None
    
    if func == 'SUM':
        return sum(values)
    elif func == 'AVG':
        return sum(values) / len(values)
    elif func == 'MIN':
        return min(values)
    elif func == 'MAX':
        return max(values)
    
    raise ValueError(f"Unknown aggregate function: {func}")


def compute(doc: TMDDocument, formula: str | None = None) -> dict[str, Any]:
    """
    Compute all computed fields, or a specific formula.
    
    If formula is None, computes all fields defined in schema.computed.
    """
    if formula:
        return {"result": _eval_formula(doc, formula)}
    
    results = {}
    for name, formula in doc.schema.computed.items():
        try:
            results[name] = _eval_formula(doc, formula)
        except Exception as e:
            results[name] = f"Error: {e}"
    
    return results


def _eval_formula(doc: TMDDocument, formula: str) -> Any:
    """Evaluate a formula against the document."""
    formula = formula.strip()
    
    # Handle COUNT(WHERE ...) - no field, just condition
    count_where_match = re.match(
        r'^COUNT\(\s*WHERE\s+(.+)\)$',
        formula, re.IGNORECASE
    )
    if count_where_match:
        where = count_where_match.group(1)
        return _compute_aggregate(doc, 'COUNT', None, where)
    
    # Direct aggregate with WHERE inside parens: SUM(amount WHERE paid=false)
    agg_match = re.match(
        r'^(SUM|AVG|COUNT|MIN|MAX)\(([^)]*?)(?:\s+WHERE\s+([^)]+))?\)$', 
        formula, re.IGNORECASE
    )
    if agg_match:
        func, field, where = agg_match.groups()
        return _compute_aggregate(doc, func.upper(), field.strip() if field else None, where)
    
    raise ValueError(f"Cannot evaluate formula: {formula}")


def resolve_refs(doc: TMDDocument, base_path: Path | None = None) -> dict[str, TMDDocument]:
    """
    Find and load all referenced documents.
    
    Returns a dict mapping ref paths to loaded TMDDocuments.
    """
    if not base_path and doc.path:
        base_path = doc.path.parent
    
    refs: dict[str, TMDDocument] = {}
    
    for row in doc.rows:
        for field, value in row.items():
            if isinstance(value, dict) and "_ref" in value:
                ref_path = value["_ref"]
                if ref_path not in refs and base_path:
                    full_path = base_path / f"{ref_path}.tmd"
                    if full_path.exists():
                        refs[ref_path] = parse_file(full_path)
    
    return refs
