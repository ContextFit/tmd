from pathlib import Path

import pytest

from tmd.ops import append_row, get_row, list_rows, parse_field_assignments, update_row, validate_file


def make_file(tmp_path: Path) -> Path:
    path = tmp_path / "tasks.tmd"
    path.write_text("""---
schema:
  id: int (pk)
  name: text
  done: bool
---

# Tasks

tasks[1]: name=Buy milk, done=false
""")
    return path


def test_parse_field_assignments_typed_values():
    fields = parse_field_assignments(["name=Acme Corp", "amount=42.5", "paid=false"])
    assert fields == {"name": "Acme Corp", "amount": 42.5, "paid": False}


def test_append_get_update_row(tmp_path):
    path = make_file(tmp_path)

    appended = append_row(path, {"name": "Call Sam", "done": False})
    assert appended["_id"] == 2
    assert appended["name"] == "Call Sam"

    row = get_row(path, 2)
    assert row["_table"] == "tasks"
    assert row["done"] is False

    updated = update_row(path, 2, {"done": True})
    assert updated["done"] is True
    assert get_row(path, "2")["done"] is True

    rows = list_rows(path)
    assert [row["_id"] for row in rows] == [1, 2]


def test_append_rejects_duplicate_id(tmp_path):
    path = make_file(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        append_row(path, {"name": "Duplicate", "done": False}, row_id=1)


def test_validate_file_json_result(tmp_path):
    path = make_file(tmp_path)
    result = validate_file(path)
    assert result["ok"] is True
    assert result["row_count"] == 1
