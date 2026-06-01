# TMD Edit Operations

Status: draft 0.1

This document defines semantic mutations a UI or agent should perform on TMD files.

## List Rows

Use:

```bash
tmd rows path/to/file.tmd --json
```

## Get Row

Use:

```bash
tmd row path/to/file.tmd ROW_ID --json
```

## Append Row

Use:

```bash
tmd append-row path/to/file.tmd --set field=value --json
```

The writer should allocate IDs according to the table's existing row pattern.

## Update Row

Use:

```bash
tmd update-row path/to/file.tmd ROW_ID --set field=value --json
```

Do not rewrite the whole file for a normal field edit.

## Schema-Aware Editing

The UI should use schema fields for:

- field order
- type hints
- required/optional state
- primary key display
- reference behavior

## Rename Row ID

Renaming row IDs is a higher-risk operation. A UI should update or report affected references before saving.

## Delete Row

Deleting rows should require explicit confirmation and should report likely affected references.

## Validate Before Save

Always validate before save or sync:

```bash
tmd validate path/to/file.tmd --json
```
