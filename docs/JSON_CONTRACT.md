# TMD JSON Contract

Status: draft 0.1

The TMD JSON contract is the reference interchange shape for renderers, UI agents, ingestion pipelines, and tests.

Generate it with:

```bash
tmd export examples/invoices.tmd --format json
```

## Top-Level Shape

```json
{
  "meta": {
    "title": "Invoices",
    "table": "invoices",
    "schema": {}
  },
  "data": []
}
```

## Meta

```json
{
  "title": "Invoices",
  "table": "invoices",
  "schema": {
    "id": {
      "type": "int",
      "nullable": false,
      "pk": true
    }
  }
}
```

## Row

```json
{
  "_id": 1,
  "name": "Q1 Consulting",
  "company": {
    "_ref": "companies/acme"
  },
  "amount": 1500.0,
  "paid": false
}
```

## Row Operation Results

`tmd rows --json` returns an array of row objects.

`tmd row ROW_ID --json`, `tmd append-row --json`, and `tmd update-row --json` return a row object.

`tmd validate --json` returns:

```json
{
  "ok": true,
  "path": "examples/invoices.tmd",
  "row_count": 5,
  "errors": [],
  "warnings": []
}
```

## Compatibility Rules

- Unknown top-level fields should be ignored.
- Unknown row fields should be preserved.
- Row `_id` values are stable handles.
- Reference objects with `_ref` should be preserved.
- UI state that is not semantically meaningful should live outside TMD.
