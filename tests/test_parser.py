"""Tests for TMD parser."""

import pytest
from tmd.parser import parse, parse_file, TMDDocument, Row


def test_parse_simple_row():
    content = """# Tasks

tasks[1]: name=Buy milk, done=false
tasks[2]: name=Call mom, done=true
"""
    doc = parse(content)
    assert doc.title == "Tasks"
    assert len(doc.rows) == 2
    assert doc.rows[0].id == 1
    assert doc.rows[0]["name"] == "Buy milk"
    assert doc.rows[0]["done"] is False
    assert doc.rows[1]["done"] is True


def test_parse_with_schema():
    content = """---
schema:
  id: int (pk)
  name: text
  amount: decimal?
---

# Items

items[1]: name=Widget, amount=99.99
items[2]: name=Gadget
"""
    doc = parse(content)
    assert "id" in doc.schema.fields
    assert doc.schema.fields["id"]["pk"] is True
    assert doc.schema.fields["amount"]["nullable"] is True
    assert doc.rows[0]["amount"] == 99.99
    assert doc.rows[1].get("amount") is None


def test_parse_quoted_values():
    content = """# Contacts

contacts[1]: name="Smith, John", title="CEO, Founder"
contacts[2]: name=Jane Doe, title=Engineer
"""
    doc = parse(content)
    assert doc.rows[0]["name"] == "Smith, John"
    assert doc.rows[0]["title"] == "CEO, Founder"
    assert doc.rows[1]["name"] == "Jane Doe"


def test_parse_references():
    content = """# Invoices

invoices[1]: name=Order, company=[[companies/acme]]
"""
    doc = parse(content)
    assert doc.rows[0]["company"] == {"_ref": "companies/acme"}


def test_parse_lists():
    content = """# Products

products[1]: name=Widget, tags=[urgent, review, v2]
"""
    doc = parse(content)
    assert doc.rows[0]["tags"] == ["urgent", "review", "v2"]


def test_parse_computed():
    content = """---
computed:
  total: SUM(amount)
  avg: AVG(amount)
---

# Sales

sales[1]: amount=100
sales[2]: amount=200
"""
    doc = parse(content)
    assert "total" in doc.schema.computed
    assert doc.schema.computed["total"] == "SUM(amount)"


def test_filter():
    content = """# Tasks

tasks[1]: name=Task A, status=done
tasks[2]: name=Task B, status=pending
tasks[3]: name=Task C, status=done
"""
    doc = parse(content)
    done = doc.filter(status="done")
    assert len(done) == 2
    assert done[0]["name"] == "Task A"
    assert done[1]["name"] == "Task C"


def test_getitem_by_id():
    content = """# Items

items[widget]: name=Widget, price=10
items[gadget]: name=Gadget, price=20
"""
    doc = parse(content)
    assert doc["widget"]["name"] == "Widget"
    assert doc["gadget"]["price"] == 20


def test_to_dicts():
    content = """# Items

items[1]: name=A, value=1
items[2]: name=B, value=2
"""
    doc = parse(content)
    dicts = doc.to_dicts()
    assert len(dicts) == 2
    assert dicts[0] == {"_id": 1, "name": "A", "value": 1}
