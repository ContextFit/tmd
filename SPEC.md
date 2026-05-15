# TMD: Tabular Markdown Specification

**Version:** 0.1.0  
**Status:** Draft

TMD is a markdown-based format for storing structured, tabular data in a way that is:
- Human-readable and editable
- Git-friendly (clean diffs)
- Token-efficient for LLM context
- Agent-native (live queries, cross-file references)
- Compatible with existing markdown tooling

---

## File Structure

A TMD file consists of:

1. **YAML Front Matter** (optional) — Schema, metadata, computed field specs
2. **Heading** — Table name (H1)
3. **Data Rows** — One record per line
4. **Prose Sections** (optional) — Notes, related links, documentation

```markdown
---
type: table
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

---

## Row Syntax

### Basic Format

```
table_name[id]: field=value, field2=value2, field3=value3
```

- `table_name` — Name of the table (should match H1 heading)
- `id` — Unique identifier for this row (can be int, string, or auto)
- Fields are `key=value` pairs separated by `, `

### Identifiers

```
invoices[1]: ...           # Integer ID
invoices[inv-001]: ...     # String ID  
invoices[]: ...            # Auto-generate ID
contacts[john-smith]: ...  # Slug ID
```

### Values

**Unquoted** — Simple values without special characters:
```
name=Acme Corp, amount=1500, paid=false
```

**Quoted** — Values containing `, ` or `=` or leading/trailing whitespace:
```
name="Smith, John", notes="Amount = $500", title=" CEO "
```

**Escape sequences** in quoted values:
- `\"` — Literal quote
- `\\` — Literal backslash

**Multiline** — For long text, use indented block:
```
invoices[3]: name=Foo LLC, amount=2200
  notes: |
    This is a longer note.
    It can span multiple lines.
    Commas, quotes, "anything" works here.
```

### Data Types

| Type | Examples | Notes |
|------|----------|-------|
| `text` | `name=John Smith` | Default type |
| `int` | `count=42` | Integer |
| `decimal` | `amount=1500.50` | Decimal number |
| `bool` | `paid=true`, `active=false` | Boolean |
| `date` | `due=2026-05-15` | ISO 8601 date |
| `datetime` | `created=2026-05-15T10:30:00Z` | ISO 8601 datetime |
| `ref` | `company=[[companies/acme]]` | Reference to another file |
| `list` | `tags=[urgent, review]` | List of values |
| `null` | `notes=null` | Explicit null |

---

## References (Foreign Keys)

Use wiki-style links to reference other files:

```
invoices[1]: name=Q1 Services, company=[[companies/acme]], contact=[[contacts/john]]
```

Reference formats:
- `[[path/to/file]]` — Reference by path
- `[[file#row-id]]` — Reference specific row in file
- `[[file|Display Text]]` — With display text

Cross-file computed example:
```yaml
computed:
  company_name: LOOKUP(company, name)  # Follow ref, get field
  total_by_company: SUM(amount GROUP BY company)
```

---

## Schema Definition

In YAML front matter:

```yaml
schema:
  id: int (pk)                    # Primary key
  name: text                       # Required text field
  amount: decimal                  # Required decimal
  company: ref(companies)          # Foreign key to companies table
  notes: text?                     # Optional (nullable)
  tags: list(text)                 # List of text values
  status: enum(draft, sent, paid)  # Enumerated values
  created: datetime = now()        # Default value
```

### Type Modifiers

- `(pk)` — Primary key
- `?` — Optional/nullable
- `= value` — Default value
- `ref(table)` — Foreign key reference
- `list(type)` — List of type
- `enum(a, b, c)` — Enumerated values

---

## Computed Fields

Define formulas that are evaluated at query time:

```yaml
computed:
  total_revenue: SUM(amount)
  outstanding: SUM(amount WHERE paid=false)
  avg_invoice: AVG(amount)
  count: COUNT()
  latest_due: MAX(due_date)
```

### Supported Functions

| Function | Description |
|----------|-------------|
| `SUM(field)` | Sum of field values |
| `AVG(field)` | Average of field values |
| `COUNT()` | Count of rows |
| `MIN(field)` | Minimum value |
| `MAX(field)` | Maximum value |
| `LOOKUP(ref, field)` | Follow reference, get field |

### Filters

```yaml
computed:
  unpaid_total: SUM(amount WHERE paid=false)
  acme_revenue: SUM(amount WHERE company=[[companies/acme]])
  recent_count: COUNT(WHERE created > 2026-01-01)
```

---

## Prose Sections

After data rows, include any markdown content:

```markdown
# Invoices

invoices[1]: name=Acme, amount=1500, paid=false

## Notes
- Follow up with [[contacts/john]] on Friday
- See [[policies/payment-terms]] for net-30 details

## Related
- [[projects/acme-q1]]
- [[reports/monthly-revenue]]
```

---

## File Organization

Recommended structure:

```
data/
  invoices.tmd           # Main invoices table
  companies/
    acme.tmd             # Company record (can have nested data)
    widget-inc.tmd
  contacts/
    john-smith.tmd
  policies/
    payment-terms.md     # Regular markdown, referenced from TMD
```

Single-record files:
```markdown
---
type: record
schema:
  name: text
  industry: text
  website: text
  contacts: list(ref(contacts))
---

# Acme Corp

name: Acme Corporation
industry: Manufacturing
website: https://acme.example.com
contacts:
  - [[contacts/john-smith]]
  - [[contacts/jane-doe]]

## Notes
Key account, handle with care.
```

---

## Indexing for ContextFit

TMD files are designed for token-native indexing:

1. **Self-describing rows** — Each row contains field names
2. **Schema as context** — Prepend schema to chunks if separated
3. **Reference graph** — Build edges from wiki links
4. **Semantic chunking** — Chunk by row boundaries when possible

### Chunk Strategy

- Small tables (< 512 tokens): Single chunk with schema
- Large tables: Chunk by N rows, prepend schema to each chunk
- Records with prose: Treat as document with structured header

---

## CLI Usage

```bash
# Parse and validate
tmd validate invoices.tmd

# Query data
tmd query invoices.tmd "SELECT * WHERE paid=false"
tmd query invoices.tmd "SUM(amount)"

# Format/prettify
tmd fmt invoices.tmd

# Export
tmd export invoices.tmd --format json
tmd export invoices.tmd --format csv

# Import
tmd import data.csv --output invoices.tmd
```

---

## Example Files

See `examples/` directory for:
- `invoices.tmd` — Basic table with computeds
- `companies/acme.tmd` — Single record with references
- `contacts/john-smith.tmd` — Contact record
- `dashboard.tmd` — Cross-file computed summaries
