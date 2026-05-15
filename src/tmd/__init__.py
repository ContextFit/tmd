"""
TMD: Tabular Markdown

A markdown-based format for structured, tabular data that is
human-readable, git-friendly, and agent-native.
"""

__version__ = "0.1.0"

from tmd.parser import parse, parse_file, TMDDocument, Row, Schema
from tmd.query import query, compute
from tmd.writer import write, write_file
from tmd.ops import append_row, get_row, list_rows, update_row, validate_file

__all__ = [
    "parse",
    "parse_file", 
    "query",
    "compute",
    "write",
    "write_file",
    "append_row",
    "get_row",
    "list_rows",
    "update_row",
    "validate_file",
    "TMDDocument",
    "Row",
    "Schema",
]
