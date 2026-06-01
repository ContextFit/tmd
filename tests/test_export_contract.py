import json
import subprocess
import sys


def export_json() -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "tmd.cli", "export", "examples/invoices.tmd", "--format", "json"],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_export_contract_top_level_shape():
    data = export_json()

    assert set(data) == {"meta", "data"}
    assert set(data["meta"]) == {"title", "table", "schema"}
    assert data["meta"]["title"] == "Invoices"
    assert data["meta"]["table"] == "invoices"
    assert data["data"]


def test_export_contract_row_shape():
    data = export_json()

    row = data["data"][0]
    assert "_id" in row
    assert "name" in row
    assert "company" in row
    assert "_ref" in row["company"]
