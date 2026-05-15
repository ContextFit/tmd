"""Tests for TMD query."""

import pytest
from tmd.parser import parse
from tmd.query import query, compute


@pytest.fixture
def invoice_doc():
    content = """---
computed:
  total: SUM(amount)
  unpaid: SUM(amount WHERE paid=false)
  count_unpaid: COUNT(WHERE paid=false)
---

# Invoices

invoices[1]: name=A, amount=100, paid=false
invoices[2]: name=B, amount=200, paid=true
invoices[3]: name=C, amount=150, paid=false
"""
    return parse(content)


def test_sum(invoice_doc):
    result = query(invoice_doc, "SUM(amount)")
    assert result == 450


def test_sum_with_where(invoice_doc):
    result = query(invoice_doc, "SUM(amount WHERE paid=false)")
    assert result == 250  # 100 + 150


def test_count(invoice_doc):
    result = query(invoice_doc, "COUNT()")
    assert result == 3


def test_count_with_where(invoice_doc):
    result = query(invoice_doc, "COUNT(WHERE paid=false)")
    assert result == 2


def test_avg(invoice_doc):
    result = query(invoice_doc, "AVG(amount)")
    assert result == 150  # 450 / 3


def test_min_max(invoice_doc):
    assert query(invoice_doc, "MIN(amount)") == 100
    assert query(invoice_doc, "MAX(amount)") == 200


def test_where_filter(invoice_doc):
    result = query(invoice_doc, "WHERE paid=false")
    assert len(result) == 2
    assert result[0].id == 1
    assert result[1].id == 3


def test_compute_all(invoice_doc):
    results = compute(invoice_doc)
    assert results["total"] == 450
    assert results["unpaid"] == 250
    assert results["count_unpaid"] == 2


def test_numeric_comparison():
    content = """# Items

items[1]: name=A, price=50
items[2]: name=B, price=100
items[3]: name=C, price=150
"""
    doc = parse(content)
    
    result = query(doc, "WHERE price>75")
    assert len(result) == 2
    
    result = query(doc, "WHERE price>=100")
    assert len(result) == 2
    
    result = query(doc, "WHERE price<100")
    assert len(result) == 1
